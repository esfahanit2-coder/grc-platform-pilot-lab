from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.tenancy.services import resolve_tenant_for_request

from .clients import connector_for
from .models import ConnectorConfig, ConnectorRun
from .serializers import ConnectorConfigSerializer, ConnectorRunSerializer
from .services import run_connector


class TenantMixin:
    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant


class ConnectorConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = ConnectorConfigSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "connector.view")
        qs = ConnectorConfig.objects.filter(tenant=tenant, deleted_at__isnull=True)
        if not has_whole_tenant_permission(self.request.user, tenant, "connector.view"):
            allowed = accessible_organization_unit_ids(self.request.user, tenant, "connector.view")
            qs = qs.filter(organization_unit_id__in=allowed)
        return qs.order_by("name")

    def _validate_unit(self, unit, perm):
        tenant = self._tenant()
        if unit:
            if unit.tenant_id != tenant.id:
                raise ValidationError("Organization unit belongs to another tenant.")
            require_tenant_permission(self.request.user, tenant, perm, unit)
        else:
            require_whole_tenant_permission(self.request.user, tenant, perm)

    @staticmethod
    def _require_active(cfg):
        if not cfg.is_active:
            raise ValidationError("Connector is inactive.")

    def perform_create(self, serializer):
        tenant = self._tenant()
        self._validate_unit(serializer.validated_data.get("organization_unit"), "connector.manage")
        serializer.save(tenant=tenant)

    def perform_update(self, serializer):
        target = serializer.validated_data.get("organization_unit", serializer.instance.organization_unit)
        self._validate_unit(target, "connector.manage")
        serializer.save()

    def perform_destroy(self, instance):
        self._validate_unit(instance.organization_unit, "connector.manage")
        from django.utils import timezone

        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active", "updated_at"])

    @action(detail=True, methods=["post"])
    def health(self, request, pk=None):
        cfg = self.get_object()
        self._validate_unit(cfg.organization_unit, "connector.run")
        self._require_active(cfg)
        try:
            result = connector_for(cfg).health()
        except Exception:
            record_audit_event(
                request.user,
                cfg.tenant,
                "connector.health",
                "connector_config",
                cfg.id,
                outcome="failure",
                metadata={"connector_type": cfg.connector_type},
                request=request,
            )
            raise
        record_audit_event(
            request.user,
            cfg.tenant,
            "connector.health",
            "connector_config",
            cfg.id,
            metadata={"connector_type": cfg.connector_type},
            request=request,
        )
        return Response(result)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        cfg = self.get_object()
        self._validate_unit(cfg.organization_unit, "connector.run")
        self._require_active(cfg)
        run, evidence = run_connector(cfg, user=request.user, request=request)
        return Response({"run_id": str(run.id), "evidence_id": str(evidence.id), "status": run.status})


class ConnectorRunViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConnectorRunSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "connector.view")
        qs = ConnectorRun.objects.filter(connector__tenant=tenant).select_related("connector", "triggered_by")
        if not has_whole_tenant_permission(self.request.user, tenant, "connector.view"):
            allowed = accessible_organization_unit_ids(self.request.user, tenant, "connector.view")
            qs = qs.filter(connector__organization_unit_id__in=allowed)
        return qs.order_by("-started_at")

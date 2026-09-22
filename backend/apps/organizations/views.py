from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids, require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .models import OrganizationUnit
from .serializers import OrganizationTreeSerializer, OrganizationUnitSerializer


class OrganizationUnitViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationUnitSerializer

    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant

    def _permission_code(self):
        return "organization.view" if self.action in {"list", "retrieve", "tree"} else "organization.manage"

    def get_queryset(self):
        tenant = self._tenant()
        code = self._permission_code()
        require_tenant_permission(self.request.user, tenant, code)
        allowed = accessible_organization_unit_ids(self.request.user, tenant, code)
        return OrganizationUnit.objects.for_tenant(tenant).filter(id__in=allowed, deleted_at__isnull=True).select_related("parent", "manager").order_by("code")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self._tenant()
        return context

    def perform_create(self, serializer):
        tenant = self._tenant()
        parent = serializer.validated_data.get("parent")
        if parent is None:
            require_whole_tenant_permission(self.request.user, tenant, "organization.manage")
        else:
            require_tenant_permission(self.request.user, tenant, "organization.manage", parent)
        obj = serializer.save(tenant=tenant)
        record_audit_event(
            self.request.user, tenant, "organization.create", "organization_unit", obj.id,
            new_data={"code": obj.code, "name": obj.name, "parent": str(obj.parent_id or "")}, object_repr=str(obj), request=self.request,
        )

    def perform_update(self, serializer):
        tenant = self._tenant()
        instance = serializer.instance
        require_tenant_permission(self.request.user, tenant, "organization.manage", instance)
        if "parent" in serializer.validated_data and serializer.validated_data.get("parent") != instance.parent:
            new_parent = serializer.validated_data.get("parent")
            if new_parent is None:
                require_whole_tenant_permission(self.request.user, tenant, "organization.manage")
            else:
                require_tenant_permission(self.request.user, tenant, "organization.manage", new_parent)
        old = {"code": instance.code, "name": instance.name, "parent": str(instance.parent_id or ""), "manager": instance.manager_id, "status": instance.status}
        obj = serializer.save()
        new = {"code": obj.code, "name": obj.name, "parent": str(obj.parent_id or ""), "manager": obj.manager_id, "status": obj.status}
        record_audit_event(self.request.user, tenant, "organization.update", "organization_unit", obj.id, old_data=old, new_data=new, object_repr=str(obj), request=self.request)

    def perform_destroy(self, instance):
        from django.utils import timezone
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "organization.manage", instance)
        if instance.children.filter(deleted_at__isnull=True).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("A unit with active child units cannot be archived.")
        instance.deleted_at = timezone.now()
        instance.status = "archived"
        instance.save(update_fields=["deleted_at", "status", "updated_at"])
        record_audit_event(self.request.user, tenant, "organization.archive", "organization_unit", instance.id, old_data={"status": "active"}, new_data={"status": "archived"}, object_repr=str(instance), request=self.request)

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "organization.view")
        allowed_ids = set(accessible_organization_unit_ids(request.user, tenant, "organization.view"))
        qs = OrganizationUnit.objects.for_tenant(tenant).filter(id__in=allowed_ids, deleted_at__isnull=True).select_related("manager").order_by("code")
        # A scoped root is a node whose parent is outside the accessible set (or truly root).
        roots = [unit for unit in qs if unit.parent_id is None or unit.parent_id not in allowed_ids]
        return Response(OrganizationTreeSerializer(roots, many=True, context={"allowed_ids": allowed_ids}).data)

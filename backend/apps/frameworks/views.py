from django.db.models import Q
import hashlib
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.identity.services import require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .exporters import version_as_json_response, version_as_xlsx_response
from .importers import commit_pack, parse_pack
from .models import Framework, FrameworkVersion, Requirement, RequirementMapping
from .serializers import FrameworkSerializer, FrameworkVersionSerializer, RequirementMappingSerializer, RequirementSerializer
from .services import (
    duplicate_framework,
    lock_framework_version,
    require_editable_version,
    require_local_framework,
    visible_frameworks,
)


class TenantFrameworkMixin:
    permission_view = "framework.view"
    permission_manage = "framework.manage"

    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self._tenant()
        return context

    def _require(self, manage=False):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, self.permission_manage if manage else self.permission_view)
        return tenant


class FrameworkViewSet(TenantFrameworkMixin, viewsets.ModelViewSet):
    serializer_class = FrameworkSerializer

    def get_queryset(self):
        tenant = self._require(manage=self.action not in {"list", "retrieve", "duplicate"})
        qs = visible_frameworks(tenant).select_related("tenant").prefetch_related("versions")
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(code__icontains=search) | Q(name__icontains=search) | Q(publisher__icontains=search))
        framework_type = self.request.query_params.get("type")
        if framework_type:
            qs = qs.filter(framework_type=framework_type)
        return qs.order_by("name")

    def perform_create(self, serializer):
        tenant = self._require(manage=True)
        obj = serializer.save(tenant=tenant, created_by=self.request.user, content_source=Framework.ContentSource.CUSTOMER)
        record_audit_event(self.request.user, tenant, "framework.create", "framework", obj.id, new_data={"code": obj.code, "name": obj.name}, object_repr=str(obj), request=self.request)

    def perform_update(self, serializer):
        tenant = self._require(manage=True)
        require_local_framework(serializer.instance, tenant)
        old = {"code": serializer.instance.code, "name": serializer.instance.name, "status": serializer.instance.status}
        obj = serializer.save()
        record_audit_event(self.request.user, tenant, "framework.update", "framework", obj.id, old_data=old, new_data={"code": obj.code, "name": obj.name, "status": obj.status}, object_repr=str(obj), request=self.request)

    def perform_destroy(self, instance):
        tenant = self._require(manage=True)
        require_local_framework(instance, tenant)
        if instance.versions.filter(is_locked=True, deleted_at__isnull=True).exists():
            raise ValidationError("A framework with locked versions cannot be archived.")
        instance.status = Framework.Status.ARCHIVED
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["status", "deleted_at", "updated_at"])
        record_audit_event(self.request.user, tenant, "framework.archive", "framework", instance.id, object_repr=str(instance), request=self.request)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "framework.manage")
        source = self.get_object()
        code = str(request.data.get("code") or "").strip()
        if not code:
            raise ValidationError({"code": "A new framework code is required."})
        clone = duplicate_framework(source, tenant, request.user, code=code, name=request.data.get("name"), version_id=request.data.get("version_id"))
        record_audit_event(request.user, tenant, "framework.duplicate", "framework", clone.id, metadata={"source_id": str(source.id)}, object_repr=str(clone), request=request)
        return Response(FrameworkSerializer(clone, context={"tenant": tenant, "request": request}).data, status=status.HTTP_201_CREATED)


class FrameworkVersionViewSet(TenantFrameworkMixin, viewsets.ModelViewSet):
    serializer_class = FrameworkVersionSerializer

    def get_queryset(self):
        tenant = self._require(manage=self.action not in {"list", "retrieve", "export"})
        qs = FrameworkVersion.objects.filter(framework__in=visible_frameworks(tenant), deleted_at__isnull=True).filter(
            Q(framework__tenant=tenant) | Q(framework__tenant__isnull=True, status=FrameworkVersion.Status.ACTIVE)
        ).select_related("framework")
        framework_id = self.request.query_params.get("framework")
        if framework_id:
            qs = qs.filter(framework_id=framework_id)
        return qs.order_by("framework__name", "-created_at")

    def perform_create(self, serializer):
        tenant = self._require(manage=True)
        obj = serializer.save(created_by=self.request.user)
        record_audit_event(self.request.user, tenant, "framework_version.create", "framework_version", obj.id, new_data={"framework": str(obj.framework_id), "version_code": obj.version_code}, object_repr=str(obj), request=self.request)

    def perform_update(self, serializer):
        tenant = self._require(manage=True)
        require_editable_version(serializer.instance, tenant)
        obj = serializer.save()
        record_audit_event(self.request.user, tenant, "framework_version.update", "framework_version", obj.id, object_repr=str(obj), request=self.request)

    def perform_destroy(self, instance):
        tenant = self._require(manage=True)
        require_editable_version(instance, tenant)
        if instance.requirements.filter(deleted_at__isnull=True).exists():
            raise ValidationError("A version containing requirements cannot be deleted; archive the framework instead.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "framework.manage")
        version = self.get_object()
        lock_framework_version(version, tenant)
        record_audit_event(request.user, tenant, "framework_version.lock", "framework_version", version.id, new_data={"checksum": version.checksum}, object_repr=str(version), request=request)
        return Response(self.get_serializer(version).data)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "framework.view")
        version = self.get_object()
        fmt = request.query_params.get("format", "json").lower()
        record_audit_event(request.user, tenant, "framework_version.export", "framework_version", version.id, metadata={"format": fmt}, object_repr=str(version), request=request)
        if fmt == "xlsx":
            return version_as_xlsx_response(version)
        return version_as_json_response(version)


class RequirementViewSet(TenantFrameworkMixin, viewsets.ModelViewSet):
    serializer_class = RequirementSerializer

    def get_queryset(self):
        tenant = self._require(manage=self.action not in {"list", "retrieve", "tree"})
        qs = Requirement.objects.filter(framework_version__framework__in=visible_frameworks(tenant), deleted_at__isnull=True).filter(
            Q(framework_version__framework__tenant=tenant) | Q(framework_version__framework__tenant__isnull=True, framework_version__status=FrameworkVersion.Status.ACTIVE)
        ).select_related("framework_version__framework", "parent").prefetch_related("translations")
        version_id = self.request.query_params.get("framework_version")
        if version_id:
            qs = qs.filter(framework_version_id=version_id)
        parent = self.request.query_params.get("parent")
        if parent == "root":
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(code__icontains=search) | Q(title__icontains=search) | Q(body__icontains=search))
        return qs.order_by("sort_order", "code")

    def perform_create(self, serializer):
        tenant = self._require(manage=True)
        obj = serializer.save()
        record_audit_event(self.request.user, tenant, "requirement.create", "requirement", obj.id, new_data={"code": obj.code, "version": str(obj.framework_version_id)}, object_repr=str(obj), request=self.request)

    def perform_update(self, serializer):
        tenant = self._require(manage=True)
        require_editable_version(serializer.instance.framework_version, tenant)
        old = {"code": serializer.instance.code, "title": serializer.instance.title, "parent": str(serializer.instance.parent_id or "")}
        obj = serializer.save()
        record_audit_event(self.request.user, tenant, "requirement.update", "requirement", obj.id, old_data=old, new_data={"code": obj.code, "title": obj.title, "parent": str(obj.parent_id or "")}, object_repr=str(obj), request=self.request)

    def perform_destroy(self, instance):
        tenant = self._require(manage=True)
        require_editable_version(instance.framework_version, tenant)
        if instance.children.filter(deleted_at__isnull=True).exists():
            raise ValidationError("A requirement with children cannot be deleted.")
        if instance.outgoing_mappings.exists() or instance.incoming_mappings.exists():
            raise ValidationError("A mapped requirement cannot be deleted.")
        instance.delete()

    @action(detail=False, methods=["get"])
    def tree(self, request):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "framework.view")
        version_id = request.query_params.get("framework_version")
        if not version_id:
            raise ValidationError({"framework_version": "framework_version is required."})
        qs = list(self.get_queryset().filter(framework_version_id=version_id))
        by_parent = {}
        for req in qs:
            by_parent.setdefault(req.parent_id, []).append(req)

        def node(req):
            data = RequirementSerializer(req, context={"tenant": tenant, "request": request}).data
            data["children"] = [node(child) for child in by_parent.get(req.id, [])]
            return data

        return Response([node(req) for req in by_parent.get(None, [])])


class RequirementMappingViewSet(TenantFrameworkMixin, viewsets.ModelViewSet):
    serializer_class = RequirementMappingSerializer
    permission_view = "framework.mapping.view"
    permission_manage = "framework.mapping.manage"

    def get_queryset(self):
        tenant = self._require(manage=self.action not in {"list", "retrieve"})
        qs = RequirementMapping.objects.filter(tenant=tenant, deleted_at__isnull=True).select_related(
            "source_requirement__framework_version__framework", "target_requirement__framework_version__framework", "reviewed_by"
        )
        source_fw = self.request.query_params.get("source_framework")
        target_fw = self.request.query_params.get("target_framework")
        if source_fw:
            qs = qs.filter(source_requirement__framework_version__framework_id=source_fw)
        if target_fw:
            qs = qs.filter(target_requirement__framework_version__framework_id=target_fw)
        return qs

    def perform_create(self, serializer):
        tenant = self._require(manage=True)
        obj = serializer.save(tenant=tenant)
        record_audit_event(self.request.user, tenant, "framework_mapping.create", "requirement_mapping", obj.id, new_data={"source": str(obj.source_requirement_id), "target": str(obj.target_requirement_id)}, request=self.request)

    def perform_update(self, serializer):
        tenant = self._require(manage=True)
        obj = serializer.save()
        record_audit_event(self.request.user, tenant, "framework_mapping.update", "requirement_mapping", obj.id, request=self.request)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "framework.mapping.manage")
        mapping = self.get_object()
        mapping.reviewed_by = request.user
        mapping.approved_at = timezone.now()
        mapping.save(update_fields=["reviewed_by", "approved_at", "updated_at"])
        record_audit_event(request.user, tenant, "framework_mapping.approve", "requirement_mapping", mapping.id, request=request)
        return Response(self.get_serializer(mapping).data)


class FrameworkImportView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "framework.import")
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "Upload a .json or .xlsx content pack."})
        raw = uploaded.read()
        source_checksum = hashlib.sha256(raw).hexdigest()
        uploaded.seek(0)
        parsed = parse_pack(uploaded)
        parsed.setdefault("version", {}).setdefault("metadata", {})["source_checksum"] = source_checksum
        dry_run = str(request.query_params.get("dry_run", "true")).lower() not in {"false", "0", "no"}
        summary = {
            "framework": parsed["framework"],
            "version": parsed["version"],
            "requirements": len(parsed["requirements"]),
            "languages": parsed["languages"],
            "errors": parsed["errors"],
            "warnings": parsed["warnings"],
            "dry_run": dry_run,
            "source_checksum": source_checksum,
        }
        if dry_run or parsed["errors"]:
            return Response(summary, status=status.HTTP_200_OK if not parsed["errors"] else status.HTTP_400_BAD_REQUEST)
        framework, version = commit_pack(parsed, tenant, request.user)
        record_audit_event(request.user, tenant, "framework.import", "framework_version", version.id, metadata={"framework_id": str(framework.id), "requirements": len(parsed["requirements"])}, object_repr=str(version), request=request)
        summary.update({"framework_id": str(framework.id), "version_id": str(version.id), "imported": True})
        return Response(summary, status=status.HTTP_201_CREATED)

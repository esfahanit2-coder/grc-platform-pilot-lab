from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.actions.models import Action
from apps.actions.serializers import ActionSerializer
from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids, has_whole_tenant_permission, require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .models import Finding
from .serializers import FindingSerializer
from .services import close_finding


class FindingViewSet(viewsets.ModelViewSet):
    serializer_class=FindingSerializer
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx
    def _perm(self):
        if self.action in {"list","retrieve"}: return "finding.view"
        if self.action=="close": return "finding.close"
        return "finding.manage"
    def get_queryset(self):
        tenant=self._tenant();code=self._perm();require_tenant_permission(self.request.user,tenant,code);allowed=accessible_organization_unit_ids(self.request.user,tenant,code);whole=has_whole_tenant_permission(self.request.user,tenant,code)
        qs=Finding.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related("organization_unit","owner","assessment_item__assessment","requirement","control_implementation__control","risk")
        if not whole: qs=qs.filter(organization_unit_id__in=allowed)
        if self.request.query_params.get("status"): qs=qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("severity"): qs=qs.filter(severity=self.request.query_params["severity"])
        if self.request.query_params.get("assessment_item"): qs=qs.filter(assessment_item_id=self.request.query_params["assessment_item"])
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(title__icontains=search)|Q(description__icontains=search)|Q(root_cause__icontains=search))
        return qs.order_by("-created_at")
    def perform_create(self,serializer):
        tenant=self._tenant();unit=serializer.validated_data.get("organization_unit") or (serializer.validated_data.get("assessment_item").assessment.organization_unit if serializer.validated_data.get("assessment_item") else None);require_tenant_permission(self.request.user,tenant,"finding.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"finding.manage")
        obj=serializer.save(tenant=tenant,organization_unit=unit);record_audit_event(self.request.user,tenant,"finding.create","finding",obj.id,new_data={"title":obj.title,"severity":obj.severity},request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant();obj=serializer.instance;require_tenant_permission(self.request.user,tenant,"finding.manage",obj.organization_unit) if obj.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"finding.manage")
        new_unit=serializer.validated_data.get("organization_unit",obj.organization_unit);require_tenant_permission(self.request.user,tenant,"finding.manage",new_unit) if new_unit else require_whole_tenant_permission(self.request.user,tenant,"finding.manage")
        updated=serializer.save();record_audit_event(self.request.user,tenant,"finding.update","finding",updated.id,request=self.request)
    def perform_destroy(self,instance):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"finding.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"finding.manage")
        instance.deleted_at=timezone.now();instance.save(update_fields=["deleted_at","updated_at"])
    @action(detail=True,methods=["post"],url_path="actions")
    def create_action(self,request,pk=None):
        finding=self.get_object();tenant=self._tenant();require_tenant_permission(request.user,tenant,"finding.manage",finding.organization_unit) if finding.organization_unit else require_whole_tenant_permission(request.user,tenant,"finding.manage")
        payload=dict(request.data);payload["organization_unit"]=str(finding.organization_unit_id) if finding.organization_unit_id else None;payload["source_type"]="finding";payload["source_id"]=str(finding.id)
        serializer=ActionSerializer(data=payload,context={"tenant":tenant,"request":request});serializer.is_valid(raise_exception=True);obj=serializer.save(tenant=tenant)
        if finding.status==Finding.Status.OPEN: finding.status=Finding.Status.IN_REMEDIATION;finding.save(update_fields=["status","updated_at"])
        record_audit_event(request.user,tenant,"finding.action_create","action",obj.id,metadata={"finding_id":str(finding.id)},request=request)
        return Response(ActionSerializer(obj,context={"tenant":tenant}).data,status=status.HTTP_201_CREATED)
    @action(detail=True,methods=["post"])
    def close(self,request,pk=None):
        finding=self.get_object();tenant=self._tenant();require_tenant_permission(request.user,tenant,"finding.close",finding.organization_unit) if finding.organization_unit else require_whole_tenant_permission(request.user,tenant,"finding.close")
        force=str(request.data.get("force","")).lower() in {"1","true","yes"}
        if force and not has_whole_tenant_permission(request.user,tenant,"finding.close"): raise ValidationError({"force":"Force close requires whole-tenant finding.close permission."})
        close_finding(finding,request.user,comment=request.data.get("comment",""),force=force);record_audit_event(request.user,tenant,"finding.close","finding",finding.id,request=request)
        return Response(self.get_serializer(finding).data)

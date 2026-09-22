from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.storage import S3ObjectStorage
from apps.identity.services import accessible_organization_unit_ids, has_whole_tenant_permission, require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .malware_service import enqueue_evidence_scan
from .models import Evidence, EvidenceLink
from .serializers import EvidenceLinkSerializer, EvidenceSerializer
from .services import link_scope, store_uploaded_evidence


class EvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenceSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx
    def _perm(self): return "evidence.view" if self.action in {"list","retrieve","download"} else "evidence.manage"
    def get_queryset(self):
        tenant=self._tenant();code=self._perm();require_tenant_permission(self.request.user,tenant,code);allowed=accessible_organization_unit_ids(self.request.user,tenant,code);whole=has_whole_tenant_permission(self.request.user,tenant,code)
        qs=Evidence.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related("organization_unit","owner")
        if not whole: qs=qs.filter(organization_unit_id__in=allowed)
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(title__icontains=search)|Q(description__icontains=search)|Q(source__icontains=search))
        if self.request.query_params.get("classification"): qs=qs.filter(classification=self.request.query_params["classification"])
        return qs.order_by("-created_at")
    def perform_create(self,serializer):
        tenant=self._tenant();unit=serializer.validated_data.get("organization_unit");require_tenant_permission(self.request.user,tenant,"evidence.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        obj=serializer.save(tenant=tenant);uploaded=self.request.FILES.get("file")
        if uploaded:
            try: store_uploaded_evidence(obj,uploaded)
            except Exception:
                obj.delete()
                raise
        record_audit_event(self.request.user,tenant,"evidence.create","evidence",obj.id,new_data={"title":obj.title,"sha256":obj.sha256},request=self.request)
        if uploaded:
            enqueue_evidence_scan(obj.id)
    def perform_update(self,serializer):
        tenant=self._tenant();instance=serializer.instance;require_tenant_permission(self.request.user,tenant,"evidence.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        new_unit=serializer.validated_data.get("organization_unit",instance.organization_unit);require_tenant_permission(self.request.user,tenant,"evidence.manage",new_unit) if new_unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        obj=serializer.save();record_audit_event(self.request.user,tenant,"evidence.update","evidence",obj.id,request=self.request)
    def perform_destroy(self,instance):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"evidence.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        instance.deleted_at=timezone.now();instance.save(update_fields=["deleted_at","updated_at"])
    @action(detail=True,methods=["get"])
    def download(self,request,pk=None):
        obj=self.get_object()
        if not obj.storage_key: return Response({"detail":"Evidence has no stored file."},status=404)
        scan_status=str((obj.metadata or {}).get("malware_scan_status") or "not_scanned").lower()
        if getattr(settings,"EVIDENCE_REQUIRE_CLEAN_DOWNLOAD",False) and scan_status!="clean":
            record_audit_event(request.user,self._tenant(),"evidence.download","evidence",obj.id,outcome="denied",metadata={"malware_scan_status":scan_status,"reason":"file_not_cleared"},request=request)
            return Response({"code":"EVIDENCE_NOT_CLEARED","detail":"Evidence file is not cleared for download.","malware_scan_status":scan_status},status=status.HTTP_409_CONFLICT)
        url=S3ObjectStorage().presigned_get(obj.storage_key,expires=300)
        record_audit_event(request.user,self._tenant(),"evidence.download","evidence",obj.id,metadata={"malware_scan_status":scan_status},request=request)
        return Response({"url":url,"expires_in":300,"sha256":obj.sha256})


class EvidenceLinkViewSet(viewsets.ModelViewSet):
    serializer_class=EvidenceLinkSerializer
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"evidence.view");allowed=accessible_organization_unit_ids(self.request.user,tenant,"evidence.view");whole=has_whole_tenant_permission(self.request.user,tenant,"evidence.view");qs=EvidenceLink.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related("evidence")
        if not whole: qs=qs.filter(evidence__organization_unit_id__in=allowed)
        if self.request.query_params.get("object_type"): qs=qs.filter(object_type=self.request.query_params["object_type"])
        if self.request.query_params.get("object_id"): qs=qs.filter(object_id=self.request.query_params["object_id"])
        return qs.order_by("-created_at")
    def perform_create(self,serializer):
        tenant=self._tenant();obj_type=serializer.validated_data["object_type"];obj_id=serializer.validated_data["object_id"];evidence=serializer.validated_data["evidence"];_,unit=link_scope(tenant,obj_type,obj_id)
        if evidence.organization_unit_id:
            require_tenant_permission(self.request.user,tenant,"evidence.manage",evidence.organization_unit)
        else:
            require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        require_tenant_permission(self.request.user,tenant,"evidence.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage")
        if evidence.organization_unit_id and unit and evidence.organization_unit_id != unit.id:
            raise ValidationError({"evidence":"Evidence scope must match target scope for scoped evidence."})
        link=serializer.save(tenant=tenant);record_audit_event(self.request.user,tenant,"evidence.link","evidence_link",link.id,metadata={"object_type":obj_type,"object_id":str(obj_id)},request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant();instance=serializer.instance;_,unit=link_scope(tenant,instance.object_type,instance.object_id);require_tenant_permission(self.request.user,tenant,"evidence.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage");serializer.save()
    def perform_destroy(self,instance):
        tenant=self._tenant();_,unit=link_scope(tenant,instance.object_type,instance.object_id);require_tenant_permission(self.request.user,tenant,"evidence.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"evidence.manage");instance.delete()

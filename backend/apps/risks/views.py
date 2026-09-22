from django.db.models import Q
from django.utils import timezone
from rest_framework import status,viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response

from apps.actions.models import Action
from apps.actions.serializers import ActionSerializer
from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids,has_whole_tenant_permission,require_tenant_permission,require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .exporters import rtp_docx_response,rtp_payload
from .models import Risk,RiskCategory,RiskControl,RiskEvaluation,RiskMethodology,RiskTreatment
from .serializers import RiskCategorySerializer,RiskControlSerializer,RiskEvaluationCreateSerializer,RiskMethodologySerializer,RiskSerializer,RiskTreatmentSerializer
from .services import evaluate_risk,methodology_defaults

class TenantMixin:
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx

class RiskCategoryViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=RiskCategorySerializer
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"risk.view");return RiskCategory.objects.filter(deleted_at__isnull=True).filter(Q(tenant=tenant)|Q(tenant__isnull=True)).order_by("code")
    def perform_create(self,serializer): tenant=self._tenant();require_whole_tenant_permission(self.request.user,tenant,"risk.manage");serializer.save(tenant=tenant)
    def perform_update(self,serializer):
        tenant=self._tenant();require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        if serializer.instance.tenant_id!=tenant.id: raise PermissionDenied("Global categories are read-only.")
        serializer.save()
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        if instance.tenant_id!=tenant.id: raise PermissionDenied("Global categories are read-only.")
        if instance.children.filter(deleted_at__isnull=True).exists() or instance.risks.filter(deleted_at__isnull=True).exists(): raise ValidationError("Risk category is in use.")
        instance.deleted_at=timezone.now(); instance.save(update_fields=["deleted_at","updated_at"])

class RiskMethodologyViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=RiskMethodologySerializer
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"risk.view");return RiskMethodology.objects.filter(tenant=tenant,deleted_at__isnull=True).order_by("-is_default","name")
    def perform_create(self,serializer):
        tenant=self._tenant();require_whole_tenant_permission(self.request.user,tenant,"risk.manage");obj=serializer.save(tenant=tenant);
        if obj.is_default: RiskMethodology.objects.filter(tenant=tenant).exclude(id=obj.id).update(is_default=False)
    def perform_update(self,serializer):
        tenant=self._tenant();require_whole_tenant_permission(self.request.user,tenant,"risk.manage");obj=serializer.save()
        if obj.is_default: RiskMethodology.objects.filter(tenant=tenant).exclude(id=obj.id).update(is_default=False)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        if instance.evaluations.filter(deleted_at__isnull=True).exists(): raise ValidationError("Methodology is referenced by risk evaluations.")
        instance.deleted_at=timezone.now(); instance.status='archived'; instance.save(update_fields=["deleted_at","status","updated_at"])

class RiskViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=RiskSerializer
    def _perm(self):
        if self.action in {"list","retrieve","rtp"}: return "risk.view"
        if self.action == "evaluate": return "risk.evaluate"
        return "risk.manage"
    def get_queryset(self):
        tenant=self._tenant();code=self._perm();require_tenant_permission(self.request.user,tenant,code);allowed=accessible_organization_unit_ids(self.request.user,tenant,code);whole=has_whole_tenant_permission(self.request.user,tenant,code)
        qs=Risk.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related("organization_unit","asset","category","owner")
        if not whole: qs=qs.filter(organization_unit_id__in=allowed)
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(code__icontains=search)|Q(title__icontains=search)|Q(scenario__icontains=search))
        if self.request.query_params.get("status"): qs=qs.filter(status=self.request.query_params["status"])
        return qs.order_by("code")
    def perform_create(self,serializer):
        tenant=self._tenant();unit=serializer.validated_data.get("organization_unit");require_tenant_permission(self.request.user,tenant,"risk.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage");obj=serializer.save(tenant=tenant);record_audit_event(self.request.user,tenant,"risk.create","risk",obj.id,new_data={"code":obj.code,"title":obj.title},object_repr=str(obj),request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant();instance=serializer.instance
        require_tenant_permission(self.request.user,tenant,"risk.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        new_unit=serializer.validated_data.get("organization_unit",instance.organization_unit)
        require_tenant_permission(self.request.user,tenant,"risk.manage",new_unit) if new_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        obj=serializer.save();record_audit_event(self.request.user,tenant,"risk.update","risk",obj.id,request=self.request)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"risk.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage")
        instance.deleted_at=timezone.now(); instance.status=Risk.Status.ARCHIVED; instance.save(update_fields=["deleted_at","status","updated_at"])
    @action(detail=True,methods=["post"])
    def evaluate(self,request,pk=None):
        tenant=self._tenant();risk=self.get_object();require_tenant_permission(request.user,tenant,"risk.evaluate",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(request.user,tenant,"risk.evaluate");s=RiskEvaluationCreateSerializer(data=request.data);s.is_valid(raise_exception=True);method=s.validated_data["methodology"];row=evaluate_risk(risk=risk,methodology=method,evaluation_type=s.validated_data["evaluation_type"],likelihood=s.validated_data["likelihood"],impact=s.validated_data["impact"],user=request.user,rationale=s.validated_data.get("rationale",""));record_audit_event(request.user,tenant,"risk.evaluate","risk_evaluation",row.id,new_data={"risk":str(risk.id),"type":row.evaluation_type,"score":str(row.score),"level":row.level},request=request);return Response({"id":str(row.id),"evaluation_type":row.evaluation_type,"score":str(row.score),"level":row.level,"likelihood":str(row.likelihood),"impact":str(row.impact)},status=201)
    @action(detail=True,methods=["get"])
    def rtp(self,request,pk=None):
        risk=self.get_object();fmt=request.query_params.get("format","json").lower();return rtp_docx_response(risk) if fmt=="docx" else Response(rtp_payload(risk))

class RiskControlViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=RiskControlSerializer
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"risk.view");allowed=accessible_organization_unit_ids(self.request.user,tenant,"risk.view");whole=has_whole_tenant_permission(self.request.user,tenant,"risk.view");qs=RiskControl.objects.filter(risk__tenant=tenant,deleted_at__isnull=True).select_related("risk","control_implementation__control");return qs if whole else qs.filter(risk__organization_unit_id__in=allowed)
    def perform_create(self,serializer):
        tenant=self._tenant();risk=serializer.validated_data["risk"];require_tenant_permission(self.request.user,tenant,"risk.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage");serializer.save()
    def perform_update(self, serializer):
        tenant=self._tenant(); risk=serializer.instance.risk; require_tenant_permission(self.request.user,tenant,"risk.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage"); serializer.save()
    def perform_destroy(self, instance):
        tenant=self._tenant(); risk=instance.risk; require_tenant_permission(self.request.user,tenant,"risk.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.manage"); instance.delete()

class RiskTreatmentViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=RiskTreatmentSerializer
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"risk.view");allowed=accessible_organization_unit_ids(self.request.user,tenant,"risk.view");whole=has_whole_tenant_permission(self.request.user,tenant,"risk.view");qs=RiskTreatment.objects.filter(risk__tenant=tenant,deleted_at__isnull=True).select_related("risk","owner")
        if self.request.query_params.get("risk"): qs=qs.filter(risk_id=self.request.query_params["risk"])
        return qs if whole else qs.filter(risk__organization_unit_id__in=allowed)
    def perform_create(self,serializer):
        tenant=self._tenant();risk=serializer.validated_data["risk"];require_tenant_permission(self.request.user,tenant,"risk.treatment.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.treatment.manage");obj=serializer.save();risk.status=Risk.Status.TREATMENT;risk.save(update_fields=["status","updated_at"]);record_audit_event(self.request.user,tenant,"risk_treatment.create","risk_treatment",obj.id,request=self.request)
    def perform_update(self, serializer):
        tenant=self._tenant(); risk=serializer.instance.risk; require_tenant_permission(self.request.user,tenant,"risk.treatment.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.treatment.manage"); serializer.save()
    def perform_destroy(self, instance):
        tenant=self._tenant(); risk=instance.risk; require_tenant_permission(self.request.user,tenant,"risk.treatment.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"risk.treatment.manage")
        Action.objects.filter(tenant=tenant,source_type="risk_treatment",source_id=instance.id,deleted_at__isnull=True).update(deleted_at=timezone.now(),status=Action.Status.CANCELLED)
        instance.deleted_at=timezone.now(); instance.status=RiskTreatment.Status.CANCELLED; instance.save(update_fields=["deleted_at","status","updated_at"])
    @action(detail=True,methods=["post"],url_path="actions")
    def create_action(self, request, pk=None):
        tenant=self._tenant(); treatment=self.get_object(); risk=treatment.risk
        require_tenant_permission(request.user,tenant,"risk.treatment.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(request.user,tenant,"risk.treatment.manage")
        payload=dict(request.data); payload["organization_unit"]=str(risk.organization_unit_id) if risk.organization_unit_id else None; payload["source_type"]="risk_treatment"; payload["source_id"]=str(treatment.id)
        serializer=ActionSerializer(data=payload,context={"tenant":tenant,"request":request}); serializer.is_valid(raise_exception=True); obj=serializer.save(tenant=tenant); record_audit_event(request.user,tenant,"risk_treatment.action_create","action",obj.id,metadata={"treatment_id":str(treatment.id)},request=request); return Response(ActionSerializer(obj,context={"tenant":tenant}).data,status=201)
    @action(detail=True,methods=["post"])
    def accept(self,request,pk=None):
        tenant=self._tenant();obj=self.get_object();risk=obj.risk;require_tenant_permission(request.user,tenant,"risk.treatment.manage",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(request.user,tenant,"risk.treatment.manage");obj.approval_status=RiskTreatment.ApprovalStatus.APPROVED;obj.accepted_by=request.user;obj.accepted_at=timezone.now();obj.save(update_fields=["approval_status","accepted_by","accepted_at","updated_at"]);return Response(self.get_serializer(obj).data)

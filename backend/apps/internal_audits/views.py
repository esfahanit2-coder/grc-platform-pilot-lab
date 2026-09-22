from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids,has_whole_tenant_permission,require_tenant_permission,require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from apps.findings.models import Finding
from apps.findings.serializers import FindingSerializer
from .models import AuditPlan,AuditEngagement,AuditTeamMember,Workpaper
from .serializers import AuditPlanSerializer,AuditEngagementSerializer,AuditTeamMemberSerializer,WorkpaperSerializer
from .exporters import audit_report_docx

class TM:
    def _tenant(self):
        if not hasattr(self,'_t'): self._t=resolve_tenant_for_request(self.request)
        return self._t
    def get_serializer_context(self): c=super().get_serializer_context();c['tenant']=self._tenant();return c
    def scoped(self,qs,code,field='organization_unit_id'):
        t=self._tenant();require_tenant_permission(self.request.user,t,code);
        if has_whole_tenant_permission(self.request.user,t,code): return qs
        return qs.filter(**{f'{field}__in':accessible_organization_unit_ids(self.request.user,t,code)})

class AuditPlanViewSet(TM,viewsets.ModelViewSet):
    serializer_class=AuditPlanSerializer
    def get_queryset(self): return self.scoped(AuditPlan.objects.filter(tenant=self._tenant(),deleted_at__isnull=True).select_related('organization_unit','owner'),'internal_audit.view').order_by('-period_start')
    def perform_create(self,s):
        t=self._tenant();u=s.validated_data.get('organization_unit');require_tenant_permission(self.request.user,t,'internal_audit.manage',u) if u else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');o=s.save(tenant=t);record_audit_event(self.request.user,t,'audit_plan.create','audit_plan',o.id,request=self.request)
    def perform_update(self,s):
        t=self._tenant();o=s.instance; require_tenant_permission(self.request.user,t,'internal_audit.manage',o.organization_unit) if o.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage'); s.save()
    def perform_destroy(self,o):
        t=self._tenant();require_tenant_permission(self.request.user,t,'internal_audit.manage',o.organization_unit) if o.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');o.deleted_at=timezone.now();o.save(update_fields=['deleted_at','updated_at'])
    @action(detail=True,methods=['post'])
    def approve(self,request,pk=None):
        o=self.get_object();t=self._tenant();require_tenant_permission(request.user,t,'internal_audit.review',o.organization_unit) if o.organization_unit else require_whole_tenant_permission(request.user,t,'internal_audit.review');o.status=AuditPlan.Status.APPROVED;o.approved_by=request.user;o.approved_at=timezone.now();o.save(update_fields=['status','approved_by','approved_at','updated_at']);return Response(self.get_serializer(o).data)

class AuditEngagementViewSet(TM,viewsets.ModelViewSet):
    serializer_class=AuditEngagementSerializer
    def get_queryset(self):
        qs=self.scoped(AuditEngagement.objects.filter(tenant=self._tenant(),deleted_at__isnull=True).select_related('organization_unit','lead_auditor','framework_version'),'internal_audit.view')
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(title__icontains=search)|Q(objective__icontains=search)|Q(scope__icontains=search))
        if self.request.query_params.get("status"): qs=qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("audit_type"): qs=qs.filter(audit_type=self.request.query_params["audit_type"])
        if self.request.query_params.get("lead_auditor"): qs=qs.filter(lead_auditor_id=self.request.query_params["lead_auditor"])
        return qs.order_by('-created_at')
    def perform_create(self,s):
        t=self._tenant();u=s.validated_data.get('organization_unit');require_tenant_permission(self.request.user,t,'internal_audit.manage',u) if u else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');o=s.save(tenant=t);record_audit_event(self.request.user,t,'audit.create','audit_engagement',o.id,request=self.request)
    def perform_update(self,s):
        t=self._tenant();o=s.instance;require_tenant_permission(self.request.user,t,'internal_audit.manage',o.organization_unit) if o.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');nu=s.validated_data.get('organization_unit',o.organization_unit);require_tenant_permission(self.request.user,t,'internal_audit.manage',nu) if nu else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');s.save()
    def perform_destroy(self,o):
        t=self._tenant();require_tenant_permission(self.request.user,t,'internal_audit.manage',o.organization_unit) if o.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.manage');o.deleted_at=timezone.now();o.status=AuditEngagement.Status.CANCELLED;o.save(update_fields=['deleted_at','status','updated_at'])
    @action(detail=True,methods=['get'])
    def report(self,request,pk=None): require_tenant_permission(request.user,self._tenant(),'report.generate',self.get_object().organization_unit) if self.get_object().organization_unit else require_whole_tenant_permission(request.user,self._tenant(),'report.generate');return audit_report_docx(self.get_object())

class AuditTeamMemberViewSet(TM,viewsets.ModelViewSet):
    serializer_class=AuditTeamMemberSerializer
    def get_queryset(self):
        t=self._tenant();require_tenant_permission(self.request.user,t,'internal_audit.view');qs=AuditTeamMember.objects.filter(engagement__tenant=t,deleted_at__isnull=True).select_related('engagement__organization_unit','user');return qs if has_whole_tenant_permission(self.request.user,t,'internal_audit.view') else qs.filter(engagement__organization_unit_id__in=accessible_organization_unit_ids(self.request.user,t,'internal_audit.view'))
    def perform_create(self,s): require_tenant_permission(self.request.user,self._tenant(),'internal_audit.manage',s.validated_data['engagement'].organization_unit) if s.validated_data['engagement'].organization_unit else require_whole_tenant_permission(self.request.user,self._tenant(),'internal_audit.manage');s.save()

class WorkpaperViewSet(TM,viewsets.ModelViewSet):
    serializer_class=WorkpaperSerializer
    def get_queryset(self):
        t=self._tenant();require_tenant_permission(self.request.user,t,'internal_audit.view');qs=Workpaper.objects.filter(engagement__tenant=t,deleted_at__isnull=True).select_related('engagement__organization_unit','tester','requirement','control_implementation__control');
        if has_whole_tenant_permission(self.request.user,t,'internal_audit.view'): return qs
        return qs.filter(engagement__organization_unit_id__in=accessible_organization_unit_ids(self.request.user,t,'internal_audit.view'))
    def perform_create(self,s):
        t=self._tenant();e=s.validated_data['engagement'];require_tenant_permission(self.request.user,t,'internal_audit.perform',e.organization_unit) if e.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.perform');o=s.save();record_audit_event(self.request.user,t,'workpaper.create','audit_workpaper',o.id,request=self.request)
    def perform_update(self,s):
        t=self._tenant();e=s.instance.engagement;require_tenant_permission(self.request.user,t,'internal_audit.perform',e.organization_unit) if e.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.perform');s.save()
    def perform_destroy(self,o):
        t=self._tenant();e=o.engagement;require_tenant_permission(self.request.user,t,'internal_audit.perform',e.organization_unit) if e.organization_unit else require_whole_tenant_permission(self.request.user,t,'internal_audit.perform');o.deleted_at=timezone.now();o.save(update_fields=['deleted_at','updated_at'])
    @action(detail=True,methods=['post'])
    def review(self,request,pk=None):
        o=self.get_object();t=self._tenant();e=o.engagement;require_tenant_permission(request.user,t,'internal_audit.review',e.organization_unit) if e.organization_unit else require_whole_tenant_permission(request.user,t,'internal_audit.review');o.status=Workpaper.Status.REVIEWED;o.reviewed_by=request.user;o.reviewed_at=timezone.now();o.save(update_fields=['status','reviewed_by','reviewed_at','updated_at']);return Response(self.get_serializer(o).data)
    @action(detail=True,methods=['post'],url_path='findings')
    def create_finding(self,request,pk=None):
        wp=self.get_object();t=self._tenant();e=wp.engagement;require_tenant_permission(request.user,t,'finding.manage',e.organization_unit) if e.organization_unit else require_whole_tenant_permission(request.user,t,'finding.manage');payload=dict(request.data);payload['organization_unit']=str(e.organization_unit_id) if e.organization_unit_id else None;payload['audit_workpaper']=str(wp.id);payload.setdefault('requirement',str(wp.requirement_id) if wp.requirement_id else None);payload.setdefault('control_implementation',str(wp.control_implementation_id) if wp.control_implementation_id else None);s=FindingSerializer(data=payload,context={'tenant':t,'request':request});s.is_valid(raise_exception=True);f=s.save(tenant=t,organization_unit=e.organization_unit);return Response(FindingSerializer(f,context={'tenant':t}).data,status=status.HTTP_201_CREATED)

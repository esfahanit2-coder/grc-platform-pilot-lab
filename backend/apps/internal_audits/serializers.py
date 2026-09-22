from rest_framework import serializers
from django.utils import timezone
from apps.tenancy.models import TenantMembership
from .models import AuditPlan,AuditEngagement,AuditTeamMember,Workpaper

def member(user,tenant): return user and TenantMembership.objects.filter(tenant=tenant,user=user,is_active=True).exists()

class AuditPlanSerializer(serializers.ModelSerializer):
    owner_display=serializers.SerializerMethodField()
    class Meta:
        model=AuditPlan; fields="__all__"; read_only_fields=["tenant","approved_by","approved_at","created_at","updated_at","deleted_at"]
    def get_owner_display(self,o): return o.owner.get_full_name() or o.owner.get_username()
    def validate(self,a):
        t=self.context['tenant']; u=a.get('organization_unit',getattr(self.instance,'organization_unit',None)); owner=a.get('owner',getattr(self.instance,'owner',None))
        if u and u.tenant_id!=t.id: raise serializers.ValidationError({'organization_unit':'Unit must belong to tenant.'})
        if owner and not member(owner,t): raise serializers.ValidationError({'owner':'Owner must be an active tenant member.'})
        return a

class AuditEngagementSerializer(serializers.ModelSerializer):
    lead_display=serializers.SerializerMethodField(); organization_name=serializers.CharField(source="organization_unit.name",read_only=True); workpapers_count=serializers.SerializerMethodField(); findings_count=serializers.SerializerMethodField()
    class Meta:
        model=AuditEngagement; fields=["id","plan","organization_unit","organization_name","framework_version","title","audit_type","objective","scope","lead_auditor","lead_display","start_date","end_date","status","conclusion","metadata","requirements","controls","workpapers_count","findings_count","created_at","updated_at"]
    def get_lead_display(self,o): return o.lead_auditor.get_full_name() or o.lead_auditor.get_username()
    def get_workpapers_count(self,o): return o.workpapers.filter(deleted_at__isnull=True).count()
    def get_findings_count(self,o): return o.workpapers.filter(findings__deleted_at__isnull=True).values('findings').distinct().count()
    def validate(self,a):
        t=self.context['tenant']; u=a.get('organization_unit',getattr(self.instance,'organization_unit',None)); lead=a.get('lead_auditor',getattr(self.instance,'lead_auditor',None)); fv=a.get('framework_version',getattr(self.instance,'framework_version',None))
        plan=a.get('plan',getattr(self.instance,'plan',None))
        if plan and plan.tenant_id!=t.id: raise serializers.ValidationError({'plan':'Audit plan must belong to tenant.'})
        if u and u.tenant_id!=t.id: raise serializers.ValidationError({'organization_unit':'Unit must belong to tenant.'})
        if lead and not member(lead,t): raise serializers.ValidationError({'lead_auditor':'Lead auditor must be tenant member.'})
        if fv and fv.framework.tenant_id not in {None,t.id}: raise serializers.ValidationError({'framework_version':'Framework is not visible to tenant.'})
        for r in a.get('requirements',[]):
            if r.framework_version.framework.tenant_id not in {None,t.id}: raise serializers.ValidationError({'requirements':'Requirement is not visible to tenant.'})
        for c in a.get('controls',[]):
            if c.tenant_id!=t.id: raise serializers.ValidationError({'controls':'Control implementation must belong to tenant.'})
        return a

class AuditTeamMemberSerializer(serializers.ModelSerializer):
    user_display=serializers.SerializerMethodField()
    class Meta: model=AuditTeamMember; fields=["id","engagement","user","user_display","role","created_at"]
    def get_user_display(self,o): return o.user.get_full_name() or o.user.get_username()

class WorkpaperSerializer(serializers.ModelSerializer):
    tester_display=serializers.SerializerMethodField()
    class Meta:
        model=Workpaper; fields=["id","engagement","requirement","control_implementation","title","objective","procedure","sample","tester","tester_display","result","conclusion","status","reviewed_by","reviewed_at","created_at","updated_at"]
        read_only_fields=["reviewed_by","reviewed_at","created_at","updated_at"]
    def get_tester_display(self,o): return o.tester.get_full_name() or o.tester.get_username()
    def validate(self,a):
        t=self.context['tenant']; e=a.get('engagement',getattr(self.instance,'engagement',None)); tester=a.get('tester',getattr(self.instance,'tester',None)); ci=a.get('control_implementation',getattr(self.instance,'control_implementation',None))
        if e and e.tenant_id!=t.id: raise serializers.ValidationError({'engagement':'Engagement must belong to tenant.'})
        if self.instance is not None and 'engagement' in a and a['engagement'].id!=self.instance.engagement_id: raise serializers.ValidationError({'engagement':'Workpaper cannot be moved to another audit.'})
        req=a.get('requirement',getattr(self.instance,'requirement',None))
        if req and req.framework_version.framework.tenant_id not in {None,t.id}: raise serializers.ValidationError({'requirement':'Requirement is not visible to tenant.'})
        if tester and not member(tester,t): raise serializers.ValidationError({'tester':'Tester must be tenant member.'})
        if ci and ci.tenant_id!=t.id: raise serializers.ValidationError({'control_implementation':'Control implementation must belong to tenant.'})
        return a

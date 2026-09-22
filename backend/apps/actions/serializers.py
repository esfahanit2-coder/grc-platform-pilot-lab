from rest_framework import serializers
from apps.tenancy.models import TenantMembership
from .models import Action
class ActionSerializer(serializers.ModelSerializer):
    owner_display=serializers.SerializerMethodField()
    reviewer_display=serializers.SerializerMethodField()
    organization_name=serializers.CharField(source="organization_unit.name",read_only=True)
    class Meta:
        model=Action
        fields=["id","organization_unit","organization_name","title","description","owner","owner_display","reviewer","reviewer_display","priority","start_date","due_date","progress","status","completed_at","source_type","source_id","metadata","created_at","updated_at"]
        read_only_fields=["created_at","updated_at","owner_display","reviewer_display","organization_name","completed_at"]
    def get_owner_display(self,obj): return obj.owner.get_full_name() or obj.owner.get_username()
    def get_reviewer_display(self,obj): return (obj.reviewer.get_full_name() or obj.reviewer.get_username()) if obj.reviewer_id else None
    def validate_progress(self,value):
        if value>100: raise serializers.ValidationError("Progress must be between 0 and 100.")
        return value
    def validate(self,attrs):
        tenant=self.context["tenant"];unit=attrs.get("organization_unit") if "organization_unit" in attrs else getattr(self.instance,"organization_unit",None)
        if unit and unit.tenant_id!=tenant.id: raise serializers.ValidationError({"organization_unit":"Unit must belong to tenant."})
        for field in ("owner","reviewer"):
            user=attrs.get(field) if field in attrs else getattr(self.instance,field,None)
            if user and not TenantMembership.objects.filter(tenant=tenant,user=user,is_active=True).exists(): raise serializers.ValidationError({field:"User must be an active tenant member."})
        source_type=attrs.get("source_type") if "source_type" in attrs else getattr(self.instance,"source_type","")
        source_id=attrs.get("source_id") if "source_id" in attrs else getattr(self.instance,"source_id",None)
        if bool(source_type) != bool(source_id): raise serializers.ValidationError({"source_id":"source_type and source_id must be supplied together."})
        if source_type:
            exists=False
            if source_type=="risk_treatment":
                from apps.risks.models import RiskTreatment
                exists=RiskTreatment.objects.filter(id=source_id,risk__tenant=tenant,deleted_at__isnull=True).exists()
            elif source_type=="finding":
                from apps.findings.models import Finding
                exists=Finding.objects.filter(id=source_id,tenant=tenant,deleted_at__isnull=True).exists()
            elif source_type=="assessment_item":
                from apps.assessments.models import AssessmentItem
                exists=AssessmentItem.objects.filter(id=source_id,assessment__tenant=tenant,deleted_at__isnull=True).exists()
            else:
                raise serializers.ValidationError({"source_type":"Unsupported action source type."})
            if not exists: raise serializers.ValidationError({"source_id":"Action source does not exist in this tenant."})
        return attrs

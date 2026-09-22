from rest_framework import serializers
from apps.tenancy.models import TenantMembership
from .models import Finding


class FindingSerializer(serializers.ModelSerializer):
    owner_display = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization_unit.name", read_only=True)
    requirement_code = serializers.CharField(source="requirement.code", read_only=True)
    actions_count = serializers.SerializerMethodField()

    class Meta:
        model = Finding
        fields = [
            "id", "organization_unit", "organization_name", "assessment_item", "audit_workpaper", "requirement", "requirement_code",
            "control_implementation", "risk", "finding_type", "title", "description", "severity", "root_cause",
            "owner", "owner_display", "due_date", "status", "closed_by", "closed_at", "closure_comment",
            "metadata", "actions_count", "created_at", "updated_at",
        ]
        read_only_fields = ["closed_by", "closed_at", "closure_comment", "actions_count", "created_at", "updated_at"]

    def get_owner_display(self, obj):
        return obj.owner.get_full_name() or obj.owner.get_username()

    def get_actions_count(self, obj):
        from apps.actions.models import Action
        return Action.objects.filter(tenant=obj.tenant, source_type="finding", source_id=obj.id, deleted_at__isnull=True).count()

    def validate(self, attrs):
        tenant = self.context["tenant"]
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if owner and not TenantMembership.objects.filter(tenant=tenant, user=owner, is_active=True).exists():
            raise serializers.ValidationError({"owner": "Owner must be an active tenant member."})
        unit = attrs.get("organization_unit", getattr(self.instance, "organization_unit", None))
        assessment_item = attrs.get("assessment_item", getattr(self.instance, "assessment_item", None))
        audit_workpaper = attrs.get("audit_workpaper", getattr(self.instance, "audit_workpaper", None))
        requirement = attrs.get("requirement", getattr(self.instance, "requirement", None))
        control_implementation = attrs.get("control_implementation", getattr(self.instance, "control_implementation", None))
        risk = attrs.get("risk", getattr(self.instance, "risk", None))
        if audit_workpaper:
            if audit_workpaper.engagement.tenant_id != tenant.id:
                raise serializers.ValidationError({"audit_workpaper": "Audit workpaper must belong to tenant."})
            audit_unit = audit_workpaper.engagement.organization_unit
            if unit and audit_unit and unit.id != audit_unit.id:
                raise serializers.ValidationError({"organization_unit": "Finding scope must match audit scope."})
            unit = unit or audit_unit
            attrs.setdefault("organization_unit", audit_unit)
            if audit_workpaper.requirement_id:
                attrs.setdefault("requirement", audit_workpaper.requirement)
            if audit_workpaper.control_implementation_id:
                attrs.setdefault("control_implementation", audit_workpaper.control_implementation)
        if assessment_item:
            if assessment_item.assessment.tenant_id != tenant.id:
                raise serializers.ValidationError({"assessment_item": "Assessment item must belong to tenant."})
            assessment_unit = assessment_item.assessment.organization_unit
            if unit and assessment_unit and unit.id != assessment_unit.id:
                raise serializers.ValidationError({"organization_unit": "Finding scope must match assessment scope."})
            unit = unit or assessment_unit
            attrs.setdefault("organization_unit", assessment_unit)
            attrs.setdefault("requirement", assessment_item.requirement)
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Organization unit must belong to tenant."})
        if requirement and requirement.framework_version.framework.tenant_id not in {None, tenant.id}:
            raise serializers.ValidationError({"requirement": "Requirement is not visible to tenant."})
        if control_implementation and control_implementation.tenant_id != tenant.id:
            raise serializers.ValidationError({"control_implementation": "Control implementation must belong to tenant."})
        if risk and risk.tenant_id != tenant.id:
            raise serializers.ValidationError({"risk": "Risk must belong to tenant."})
        if self.instance is not None:
            for field in ("assessment_item", "audit_workpaper", "requirement", "control_implementation", "risk"):
                if field in attrs and getattr(attrs[field], "id", attrs[field]) != getattr(self.instance, f"{field}_id"):
                    raise serializers.ValidationError({field: "Finding source/context relationship is immutable."})
            if attrs.get("status") == Finding.Status.CLOSED and self.instance.status != Finding.Status.CLOSED:
                raise serializers.ValidationError({"status": "Use the finding close action for verified closure."})
        return attrs

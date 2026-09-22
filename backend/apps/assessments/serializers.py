from django.db.models import Count
from rest_framework import serializers
from apps.tenancy.models import TenantMembership
from .models import Assessment, AssessmentItem


def _root_objects(serializer,obj):
    instance=getattr(serializer.root,"instance",None)
    if instance is None: return [obj]
    if hasattr(instance,"pk"): return [instance]
    try: return list(instance)
    except TypeError: return [obj]


class AssessmentSerializer(serializers.ModelSerializer):
    framework_code = serializers.CharField(source="framework_version.framework.code", read_only=True)
    framework_name = serializers.CharField(source="framework_version.framework.name", read_only=True)
    version_code = serializers.CharField(source="framework_version.version_code", read_only=True)
    organization_name = serializers.CharField(source="organization_unit.name", read_only=True)
    owner_display = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    findings_count = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id", "framework_version", "framework_code", "framework_name", "version_code",
            "organization_unit", "organization_name", "title", "assessment_type", "owner", "owner_display",
            "start_date", "due_date", "status", "overall_score", "progress_percent", "metadata",
            "items_count", "findings_count", "created_at", "updated_at",
        ]
        read_only_fields = ["overall_score", "progress_percent", "created_at", "updated_at"]

    def get_owner_display(self, obj):
        return obj.owner.get_full_name() or obj.owner.get_username()

    def _count_cache(self,obj):
        cache=self.context.get("_assessment_relation_count_cache")
        if cache is not None: return cache
        ids=[row.id for row in _root_objects(self,obj)]
        item_counts={row["assessment_id"]:row["count"] for row in AssessmentItem.objects.filter(assessment_id__in=ids,deleted_at__isnull=True).values("assessment_id").annotate(count=Count("id"))}
        from apps.findings.models import Finding
        finding_counts={row["assessment_item__assessment_id"]:row["count"] for row in Finding.objects.filter(assessment_item__assessment_id__in=ids,assessment_item__deleted_at__isnull=True,deleted_at__isnull=True).values("assessment_item__assessment_id").annotate(count=Count("id"))}
        cache={"items":item_counts,"findings":finding_counts}
        self.context["_assessment_relation_count_cache"]=cache
        return cache

    def get_items_count(self, obj): return self._count_cache(obj)["items"].get(obj.id,0)

    def get_findings_count(self, obj): return self._count_cache(obj)["findings"].get(obj.id,0)

    def validate(self, attrs):
        tenant = self.context["tenant"]
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if owner and not TenantMembership.objects.filter(tenant=tenant, user=owner, is_active=True).exists():
            raise serializers.ValidationError({"owner": "Owner must be an active tenant member."})
        unit = attrs.get("organization_unit", getattr(self.instance, "organization_unit", None))
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Organization unit must belong to tenant."})
        if self.instance is not None:
            if "framework_version" in attrs and attrs["framework_version"].id != self.instance.framework_version_id:
                raise serializers.ValidationError({"framework_version": "Assessment framework/version is immutable."})
            if "organization_unit" in attrs and attrs["organization_unit"] != self.instance.organization_unit:
                raise serializers.ValidationError({"organization_unit": "Assessment scope is immutable after creation."})
            if attrs.get("status") == Assessment.Status.COMPLETED and self.instance.status != Assessment.Status.COMPLETED:
                raise serializers.ValidationError({"status": "Use the assessment complete action after review."})
        return attrs


class AssessmentItemSerializer(serializers.ModelSerializer):
    requirement_code = serializers.CharField(source="requirement_code_snapshot", read_only=True)
    requirement_title = serializers.CharField(source="requirement_title_snapshot", read_only=True)
    requirement_guidance = serializers.CharField(source="requirement.guidance", read_only=True)
    mapped_controls = serializers.SerializerMethodField()
    evidence_count = serializers.SerializerMethodField()
    findings_count = serializers.SerializerMethodField()
    assigned_to_display = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentItem
        fields = [
            "id", "assessment", "requirement", "requirement_code", "requirement_title", "requirement_guidance",
            "weight_snapshot", "status", "score", "maturity_level", "applicability", "assessor_comment",
            "reviewer_comment", "assigned_to", "assigned_to_display", "reviewed_by", "mapped_controls",
            "evidence_count", "findings_count", "created_at", "updated_at",
        ]
        read_only_fields = ["assessment", "requirement", "reviewer_comment", "reviewed_by", "created_at", "updated_at"]

    def _relation_cache(self,obj):
        cache=self.context.get("_assessment_item_relation_cache")
        if cache is not None: return cache
        objects=_root_objects(self,obj);ids=[row.id for row in objects];requirement_ids={row.requirement_id for row in objects}
        from apps.controls.models import ControlRequirement
        mapped={requirement_id:[] for requirement_id in requirement_ids}
        for row in ControlRequirement.objects.filter(requirement_id__in=requirement_ids,deleted_at__isnull=True).select_related("control"):
            bucket=mapped.setdefault(row.requirement_id,[])
            if len(bucket)<50: bucket.append(row)
        tenant=self.context.get("tenant")
        from apps.evidence.models import EvidenceLink
        evidence_qs=EvidenceLink.objects.filter(object_type="assessment_item",object_id__in=ids,deleted_at__isnull=True)
        if tenant is not None: evidence_qs=evidence_qs.filter(tenant=tenant)
        evidence={row["object_id"]:row["count"] for row in evidence_qs.values("object_id").annotate(count=Count("id"))}
        from apps.findings.models import Finding
        findings={row["assessment_item_id"]:row["count"] for row in Finding.objects.filter(assessment_item_id__in=ids,deleted_at__isnull=True).values("assessment_item_id").annotate(count=Count("id"))}
        cache={"mapped":mapped,"evidence":evidence,"findings":findings}
        self.context["_assessment_item_relation_cache"]=cache
        return cache

    def get_mapped_controls(self, obj):
        rows=self._relation_cache(obj)["mapped"].get(obj.requirement_id,[])
        return [{"id": str(row.control_id), "code": row.control.code, "title": row.control.title, "coverage": str(row.coverage)} for row in rows]

    def get_evidence_count(self, obj): return self._relation_cache(obj)["evidence"].get(obj.id,0)

    def get_findings_count(self, obj): return self._relation_cache(obj)["findings"].get(obj.id,0)

    def get_assigned_to_display(self, obj):
        return (obj.assigned_to.get_full_name() or obj.assigned_to.get_username()) if obj.assigned_to else ""

    def validate_assigned_to(self, user):
        if user is None:
            return user
        tenant = self.context["tenant"]
        if not TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
            raise serializers.ValidationError("Assigned user must be an active tenant member.")
        return user

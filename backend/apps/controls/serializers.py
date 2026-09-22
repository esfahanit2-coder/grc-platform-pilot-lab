from django.db.models import Count
from rest_framework import serializers

from apps.frameworks.models import Requirement
from apps.tenancy.models import TenantMembership
from .models import Control, ControlCategory, ControlImplementation, ControlRequirement
from .services import validate_control_requirement


def _validate_member(user, tenant, field):
    if user and not TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
        raise serializers.ValidationError(f"{field} must be an active member of the tenant.")


def _root_ids(serializer,obj):
    instance=getattr(serializer.root,"instance",None)
    if instance is None: return [obj.pk]
    if hasattr(instance,"pk"): return [instance.pk]
    try: return [row.pk for row in instance]
    except TypeError: return [obj.pk]


class ControlCategorySerializer(serializers.ModelSerializer):
    is_global = serializers.SerializerMethodField()
    class Meta:
        model = ControlCategory
        fields = ["id", "parent", "code", "name", "description", "is_global", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at", "is_global"]
    def get_is_global(self, obj): return obj.tenant_id is None


class ControlSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    frameworks_count = serializers.SerializerMethodField()
    implementations_count = serializers.SerializerMethodField()
    class Meta:
        model = Control
        fields = ["id", "code", "title", "description", "objective", "category", "category_name", "control_type", "nature", "frequency", "automation_level", "status", "metadata", "is_global", "frameworks_count", "implementations_count", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at", "is_global"]
    def _count_cache(self,obj):
        cache=self.context.get("_control_relation_count_cache")
        if cache is not None: return cache
        ids=_root_ids(self,obj)
        framework_counts={row["control_id"]:row["count"] for row in ControlRequirement.objects.filter(control_id__in=ids,deleted_at__isnull=True).values("control_id").annotate(count=Count("requirement__framework_version__framework",distinct=True))}
        implementations=ControlImplementation.objects.filter(control_id__in=ids,deleted_at__isnull=True)
        tenant=self.context.get("tenant")
        if tenant is not None: implementations=implementations.filter(tenant=tenant)
        implementation_counts={row["control_id"]:row["count"] for row in implementations.values("control_id").annotate(count=Count("id"))}
        cache={"frameworks":framework_counts,"implementations":implementation_counts}
        self.context["_control_relation_count_cache"]=cache
        return cache
    def get_frameworks_count(self, obj): return self._count_cache(obj)["frameworks"].get(obj.id,0)
    def get_implementations_count(self, obj): return self._count_cache(obj)["implementations"].get(obj.id,0)
    def validate_category(self, category):
        tenant = self.context["tenant"]
        if category and category.tenant_id not in {None, tenant.id}:
            raise serializers.ValidationError("Category is not visible to this tenant.")
        return category


class ControlRequirementSerializer(serializers.ModelSerializer):
    control_code = serializers.CharField(source="control.code", read_only=True)
    requirement_code = serializers.CharField(source="requirement.code", read_only=True)
    framework_code = serializers.CharField(source="requirement.framework_version.framework.code", read_only=True)
    class Meta:
        model = ControlRequirement
        fields = ["id", "control", "control_code", "requirement", "requirement_code", "framework_code", "coverage", "mapping_type", "rationale", "source", "approved", "created_at", "updated_at"]
        read_only_fields = ["approved", "created_at", "updated_at"]
    def validate(self, attrs):
        tenant = self.context["tenant"]
        control = attrs.get("control") or (self.instance.control if self.instance else None)
        requirement = attrs.get("requirement") or (self.instance.requirement if self.instance else None)
        if control is None or requirement is None:
            return attrs
        validate_control_requirement(control, requirement, tenant)
        return attrs


class ControlImplementationSerializer(serializers.ModelSerializer):
    control_code = serializers.CharField(source="control.code", read_only=True)
    control_title = serializers.CharField(source="control.title", read_only=True)
    organization_name = serializers.CharField(source="organization_unit.name", read_only=True)
    owner_display = serializers.SerializerMethodField()
    class Meta:
        model = ControlImplementation
        fields = ["id", "control", "control_code", "control_title", "organization_unit", "organization_name", "owner", "owner_display", "operator", "implementation_description", "implementation_status", "effectiveness", "implementation_date", "review_date", "metadata", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at", "owner_display"]
    def get_owner_display(self, obj): return obj.owner.get_full_name() or obj.owner.get_username()
    def validate(self, attrs):
        tenant = self.context["tenant"]
        control = attrs.get("control") or getattr(self.instance, "control", None)
        unit = attrs.get("organization_unit") or getattr(self.instance, "organization_unit", None)
        owner = attrs.get("owner") or getattr(self.instance, "owner", None)
        operator = attrs.get("operator") if "operator" in attrs else getattr(self.instance, "operator", None)
        if control and control.tenant_id not in {None, tenant.id}:
            raise serializers.ValidationError({"control": "Control is not visible to this tenant."})
        if control and control.tenant_id is None and control.status != Control.Status.ACTIVE:
            raise serializers.ValidationError({"control": "Only active global controls can be implemented."})
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Organization unit must belong to the tenant."})
        if self.instance is not None:
            if "control" in attrs and attrs["control"].id != self.instance.control_id:
                raise serializers.ValidationError({"control": "Control implementation cannot be moved to another control."})
            if "organization_unit" in attrs and attrs["organization_unit"].id != self.instance.organization_unit_id:
                raise serializers.ValidationError({"organization_unit": "Control implementation scope is immutable; create a new implementation instead."})
        _validate_member(owner, tenant, "owner")
        _validate_member(operator, tenant, "operator")
        return attrs


from .models import ControlTest,ControlTestRun
class ControlTestSerializer(serializers.ModelSerializer):
    control_code=serializers.CharField(source='control_implementation.control.code',read_only=True)
    class Meta: model=ControlTest; fields=["id","control_implementation","control_code","title","method","expected_result","frequency","owner","automation_type","connector_key","is_active","created_at","updated_at"]
    def validate(self,a):
        t=self.context['tenant'];ci=a.get('control_implementation',getattr(self.instance,'control_implementation',None));owner=a.get('owner',getattr(self.instance,'owner',None))
        if ci and ci.tenant_id!=t.id: raise serializers.ValidationError({'control_implementation':'Implementation must belong to tenant.'})
        _validate_member(owner,t,'owner'); return a
class ControlTestRunSerializer(serializers.ModelSerializer):
    class Meta: model=ControlTestRun; fields=["id","control_test","executed_at","executed_by","result","result_value","conclusion","next_test_date","created_at"]
    read_only_fields=['executed_by','created_at']
    def validate_control_test(self,v):
        if v.control_implementation.tenant_id!=self.context['tenant'].id: raise serializers.ValidationError('Control test must belong to tenant.')
        return v

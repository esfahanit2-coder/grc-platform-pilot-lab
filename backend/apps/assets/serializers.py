from rest_framework import serializers
from apps.tenancy.models import TenantMembership
from .models import Asset, AssetDependency

class AssetSerializer(serializers.ModelSerializer):
    organization_name=serializers.CharField(source="organization_unit.name",read_only=True)
    owner_display=serializers.SerializerMethodField()
    custodian_display=serializers.SerializerMethodField()
    cia_score=serializers.SerializerMethodField()
    class Meta:
        model=Asset
        fields=["id","organization_unit","organization_name","asset_type","code","title","description","owner","owner_display","custodian","custodian_display","confidentiality","integrity","availability","cia_score","criticality","status","metadata","created_at","updated_at"]
        read_only_fields=["created_at","updated_at","owner_display","custodian_display","cia_score"]
    def get_owner_display(self,obj): return obj.owner.get_full_name() or obj.owner.get_username()
    def get_custodian_display(self,obj): return (obj.custodian.get_full_name() or obj.custodian.get_username()) if obj.custodian_id else None
    def get_cia_score(self,obj): return round((obj.confidentiality+obj.integrity+obj.availability)/3,2)
    def validate(self,attrs):
        tenant=self.context["tenant"]; unit=attrs.get("organization_unit") or getattr(self.instance,"organization_unit",None); owner=attrs.get("owner") or getattr(self.instance,"owner",None); custodian=attrs.get("custodian") if "custodian" in attrs else getattr(self.instance,"custodian",None)
        if unit and unit.tenant_id!=tenant.id: raise serializers.ValidationError({"organization_unit":"Organization unit must belong to tenant."})
        for field,user in (("owner",owner),("custodian",custodian)):
            if user and not TenantMembership.objects.filter(tenant=tenant,user=user,is_active=True).exists(): raise serializers.ValidationError({field:f"{field} must be an active tenant member."})
        return attrs

class AssetDependencySerializer(serializers.ModelSerializer):
    parent_code=serializers.CharField(source="parent_asset.code",read_only=True)
    parent_title=serializers.CharField(source="parent_asset.title",read_only=True)
    child_code=serializers.CharField(source="child_asset.code",read_only=True)
    child_title=serializers.CharField(source="child_asset.title",read_only=True)
    class Meta:
        model=AssetDependency
        fields=["id","parent_asset","parent_code","parent_title","child_asset","child_code","child_title","dependency_type","critical","created_at"]
        read_only_fields=["created_at"]
    def validate(self,attrs):
        tenant=self.context["tenant"]; a=attrs.get("parent_asset") or (self.instance.parent_asset if self.instance else None); b=attrs.get("child_asset") or (self.instance.child_asset if self.instance else None)
        if a is None or b is None: return attrs
        if a.id==b.id: raise serializers.ValidationError("An asset cannot depend on itself.")
        if a.tenant_id!=tenant.id or b.tenant_id!=tenant.id: raise serializers.ValidationError("Both assets must belong to tenant.")
        return attrs

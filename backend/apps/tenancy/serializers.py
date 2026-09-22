from rest_framework import serializers
from .models import Tenant, TenantMembership


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "code", "tenant_type", "status", "default_language", "timezone"]


class TenantAdminSerializer(serializers.ModelSerializer):
    security = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ["id", "name", "code", "tenant_type", "status", "default_language", "timezone", "security", "created_at", "updated_at"]
        read_only_fields = ["id", "code", "created_at", "updated_at"]

    def get_security(self, tenant):
        defaults = {"require_mfa": False, "password_min_length": 12, "session_minutes": 60}
        defaults.update((tenant.settings or {}).get("security", {}))
        return defaults


class SecuritySettingsSerializer(serializers.Serializer):
    require_mfa = serializers.BooleanField(default=False)
    password_min_length = serializers.IntegerField(min_value=10, max_value=128, default=12)
    session_minutes = serializers.IntegerField(min_value=5, max_value=1440, default=60)


class MembershipTenantSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)

    class Meta:
        model = TenantMembership
        fields = ["id", "tenant", "role_code", "is_active"]

class TenantProvisionSerializer(serializers.ModelSerializer):
    admin_user_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Tenant
        fields = ["id", "name", "code", "tenant_type", "status", "default_language", "timezone", "admin_user_id"]
        read_only_fields = ["id"]

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import TenantMembership
from .models import MFADevice, Permission, Role, UserRoleScope
from .services import bootstrap_tenant_rbac

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "module", "name", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system", "is_active", "permissions", "permission_codes"]
        read_only_fields = ["is_system"]

    def validate_permission_codes(self, codes):
        known = set(Permission.objects.filter(code__in=codes, is_active=True).values_list("code", flat=True))
        missing = sorted(set(codes) - known)
        if missing:
            raise serializers.ValidationError(f"Unknown permissions: {', '.join(missing)}")
        return list(dict.fromkeys(codes))

    def create(self, validated_data):
        codes = validated_data.pop("permission_codes", [])
        role = Role.objects.create(tenant=self.context["tenant"], **validated_data)
        if codes:
            role.permissions.set(Permission.objects.filter(code__in=codes))
        return role

    def update(self, instance, validated_data):
        codes = validated_data.pop("permission_codes", None)
        if instance.is_system and "code" in validated_data and validated_data["code"] != instance.code:
            raise serializers.ValidationError({"code": "System role code cannot be changed."})
        instance = super().update(instance, validated_data)
        if codes is not None:
            instance.permissions.set(Permission.objects.filter(code__in=codes))
        return instance


class TenantUserSerializer(serializers.ModelSerializer):
    role_assignments = serializers.SerializerMethodField()
    membership_active = serializers.SerializerMethodField()
    user_active = serializers.BooleanField(source="is_active", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "user_active", "membership_active", "last_login", "role_assignments"]

    def get_membership_active(self, user):
        tenant = self.context["tenant"]
        membership = TenantMembership.objects.filter(tenant=tenant, user=user).first()
        return bool(membership and membership.is_active)

    def get_role_assignments(self, user):
        tenant = self.context["tenant"]
        qs = UserRoleScope.objects.select_related("role", "organization_unit").filter(tenant=tenant, user=user, is_active=True)
        return [
            {
                "id": str(item.id),
                "role": {"id": str(item.role_id), "code": item.role.code, "name": item.role.name},
                "organization_unit": None if not item.organization_unit_id else {
                    "id": str(item.organization_unit_id), "code": item.organization_unit.code, "name": item.organization_unit.name
                },
                "valid_from": item.valid_from,
                "valid_until": item.valid_until,
            }
            for item in qs
        ]


class TenantUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_password(self, value):
        tenant = self.context["tenant"]
        security = (tenant.settings or {}).get("security", {})
        min_length = max(int(security.get("password_min_length", 10)), 10)
        if len(value) < min_length:
            raise serializers.ValidationError(f"Password must contain at least {min_length} characters.")
        validate_password(value)
        return value

    def create(self, validated_data):
        tenant = self.context["tenant"]
        user = User.objects.create_user(**validated_data)
        TenantMembership.objects.create(tenant=tenant, user=user, role_code="member")
        bootstrap_tenant_rbac(tenant)
        return user


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_code = serializers.SlugRelatedField(source="role", slug_field="code", queryset=Role.objects.none())
    organization_unit = serializers.PrimaryKeyRelatedField(queryset=OrganizationUnit.objects.none(), allow_null=True, required=False)

    class Meta:
        model = UserRoleScope
        fields = ["id", "user", "role_code", "organization_unit", "is_active", "valid_from", "valid_until"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.context.get("tenant")
        if tenant:
            self.fields["role_code"].queryset = Role.objects.filter(tenant=tenant, is_active=True)
            self.fields["organization_unit"].queryset = OrganizationUnit.objects.for_tenant(tenant).filter(deleted_at__isnull=True)

    def validate_user(self, user):
        tenant = self.context["tenant"]
        if not TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
            raise serializers.ValidationError("User is not an active tenant member.")
        return user

    def validate(self, attrs):
        tenant = self.context["tenant"]
        role = attrs.get("role", getattr(self.instance, "role", None))
        unit = attrs.get("organization_unit", getattr(self.instance, "organization_unit", None))
        if role and role.tenant_id != tenant.id:
            raise serializers.ValidationError({"role_code": "Role must belong to the selected tenant."})
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Scope must belong to the selected tenant."})
        valid_from = attrs.get("valid_from", getattr(self.instance, "valid_from", None))
        valid_until = attrs.get("valid_until", getattr(self.instance, "valid_until", None))
        if valid_from and valid_until and valid_until < valid_from:
            raise serializers.ValidationError({"valid_until": "Role assignment end time must not be before its start time."})
        user = attrs.get("user", getattr(self.instance, "user", None))
        if user and role:
            duplicate = UserRoleScope.objects.filter(tenant=tenant, user=user, role=role, organization_unit=unit, is_active=True)
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError("This active role assignment already exists.")
        return attrs

    def create(self, validated_data):
        tenant = self.context["tenant"]
        lookup = {
            "tenant": tenant,
            "user": validated_data["user"],
            "role": validated_data["role"],
            "organization_unit": validated_data.get("organization_unit"),
        }
        existing = UserRoleScope.objects.filter(**lookup).first()
        if existing:
            existing.is_active = True
            existing.valid_from = validated_data.get("valid_from")
            existing.valid_until = validated_data.get("valid_until")
            existing.save(update_fields=["is_active", "valid_from", "valid_until", "updated_at"])
            return existing
        return UserRoleScope.objects.create(tenant=tenant, **validated_data)


class MFADeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MFADevice
        fields = ["id", "name", "is_active", "confirmed_at", "last_used_at", "created_at"]
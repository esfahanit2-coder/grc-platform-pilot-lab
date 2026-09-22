from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant


class Permission(UUIDTimeStampedModel):
    code = models.CharField(max_length=120, unique=True)
    module = models.CharField(max_length=64)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "code"]
        indexes = [models.Index(fields=["module", "is_active"])]

    def __str__(self):
        return self.code


class Role(UUIDTimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="roles")
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(Permission, through="RolePermission", related_name="roles")

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uq_role_tenant_code")]
        indexes = [models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        return f"{self.tenant.code}:{self.code}"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission")]


class UserRoleScope(UUIDTimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="grc_role_scopes")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="user_role_scopes")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    organization_unit = models.ForeignKey(
        "organizations.OrganizationUnit",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        help_text="Null means the whole tenant.",
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tenant", "role", "organization_unit"],
                name="uq_user_role_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "tenant", "role"],
                condition=models.Q(organization_unit__isnull=True),
                name="uq_user_role_whole_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "user", "is_active"]),
            models.Index(fields=["tenant", "role", "is_active"]),
        ]

    def __str__(self):
        suffix = self.organization_unit.code if self.organization_unit_id else "*"
        return f"{self.user} / {self.role.code} / {suffix}"


class MFADevice(UUIDTimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_devices")
    name = models.CharField(max_length=100, default="Authenticator")
    encrypted_secret = models.TextField()
    is_active = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    # Highest accepted TOTP time-step. Persisted so an accepted code cannot be
    # replayed across workers or requests during the same validity window.
    last_used_step = models.BigIntegerField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-is_active", "created_at"]
        indexes = [models.Index(fields=["user", "is_active"])]

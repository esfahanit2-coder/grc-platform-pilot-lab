from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel

class Tenant(UUIDTimeStampedModel):
    class TenantType(models.TextChoices):
        ENTERPRISE = "enterprise", "Enterprise"
        HOLDING = "holding", "Holding"
        CONSULTING = "consulting", "Consulting Company"
        SAAS = "saas", "SaaS Customer"

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=80, unique=True)
    tenant_type = models.CharField(max_length=20, choices=TenantType.choices, default=TenantType.ENTERPRISE)
    status = models.CharField(max_length=20, default="active")
    default_language = models.CharField(max_length=10, default="fa")
    timezone = models.CharField(max_length=64, default="Asia/Tehran")
    settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

class TenantMembership(UUIDTimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")
    role_code = models.CharField(max_length=64, default="member")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="uq_tenant_membership_user"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.tenant}"

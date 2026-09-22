from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant

class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

class OrganizationUnit(UUIDTimeStampedModel):
    class UnitType(models.TextChoices):
        HOLDING = "holding", "Holding"
        COMPANY = "company", "Company"
        BUSINESS_UNIT = "business_unit", "Business Unit"
        DEPARTMENT = "department", "Department"
        SITE = "site", "Site"
        TEAM = "team", "Team"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="organization_units")
    objects = TenantQuerySet.as_manager()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    unit_type = models.CharField(max_length=32, choices=UnitType.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, default="active")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uq_orgunit_tenant_code")]
        indexes = [models.Index(fields=["tenant", "parent"]), models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"{self.code} — {self.name}"

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class Asset(UUIDTimeStampedModel):
    class AssetType(models.TextChoices):
        INFORMATION="information","Information"
        HARDWARE="hardware","Hardware"
        SOFTWARE="software","Software"
        APPLICATION="application","Application"
        DATABASE="database","Database"
        CLOUD_SERVICE="cloud_service","Cloud service"
        SERVICE="service","Service"
        PROCESS="process","Process"
        PERSON="person","Person"
        SITE="site","Site"
        OTHER="other","Other"
    class Status(models.TextChoices):
        ACTIVE="active","Active"
        RETIRED="retired","Retired"
        ARCHIVED="archived","Archived"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="assets")
    organization_unit=models.ForeignKey(OrganizationUnit,on_delete=models.PROTECT,related_name="assets")
    asset_type=models.CharField(max_length=24,choices=AssetType.choices)
    code=models.CharField(max_length=100)
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_assets")
    custodian=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="custodied_assets")
    confidentiality=models.PositiveSmallIntegerField(default=3,validators=[MinValueValidator(1),MaxValueValidator(5)])
    integrity=models.PositiveSmallIntegerField(default=3,validators=[MinValueValidator(1),MaxValueValidator(5)])
    availability=models.PositiveSmallIntegerField(default=3,validators=[MinValueValidator(1),MaxValueValidator(5)])
    criticality=models.DecimalField(max_digits=6,decimal_places=2,default=3)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE)
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","code"],name="uq_asset_tenant_code")]
        indexes=[models.Index(fields=["tenant","organization_unit","status"]),models.Index(fields=["tenant","asset_type"])]
    def __str__(self): return f"{self.code} — {self.title}"


class AssetDependency(UUIDTimeStampedModel):
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="asset_dependencies")
    parent_asset=models.ForeignKey(Asset,on_delete=models.CASCADE,related_name="dependencies_out")
    child_asset=models.ForeignKey(Asset,on_delete=models.CASCADE,related_name="dependencies_in")
    dependency_type=models.CharField(max_length=80,default="depends_on")
    critical=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","parent_asset","child_asset","dependency_type"],name="uq_asset_dependency")]

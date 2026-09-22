from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.models import UUIDTimeStampedModel
from apps.frameworks.models import Requirement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class ControlCategory(UUIDTimeStampedModel):
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE, related_name="control_categories")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    code = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_control_category_tenant_code"),
            models.UniqueConstraint(fields=["code"], condition=Q(tenant__isnull=True), name="uq_control_category_global_code"),
        ]

    def clean(self):
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "A category cannot be its own parent."})
        if self.parent_id and self.parent.tenant_id != self.tenant_id:
            raise ValidationError({"parent": "Parent category must have the same ownership scope."})
        node=self.parent;visited=set()
        while node is not None and node.id not in visited:
            if self.id and node.id==self.id:
                raise ValidationError({"parent":"Control category hierarchy cannot contain cycles."})
            visited.add(node.id);node=node.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class Control(UUIDTimeStampedModel):
    class ControlType(models.TextChoices):
        ADMINISTRATIVE = "administrative", "Administrative"
        TECHNICAL = "technical", "Technical"
        PHYSICAL = "physical", "Physical"
        PROCESS = "process", "Process"

    class Nature(models.TextChoices):
        PREVENTIVE = "preventive", "Preventive"
        DETECTIVE = "detective", "Detective"
        CORRECTIVE = "corrective", "Corrective"
        DIRECTIVE = "directive", "Directive"

    class AutomationLevel(models.TextChoices):
        MANUAL = "manual", "Manual"
        SEMI_AUTOMATED = "semi_automated", "Semi-automated"
        AUTOMATED = "automated", "Automated"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE, related_name="controls")
    code = models.SlugField(max_length=120)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    category = models.ForeignKey(ControlCategory, null=True, blank=True, on_delete=models.PROTECT, related_name="controls")
    control_type = models.CharField(max_length=24, choices=ControlType.choices, default=ControlType.ADMINISTRATIVE)
    nature = models.CharField(max_length=24, choices=Nature.choices, default=Nature.PREVENTIVE)
    frequency = models.CharField(max_length=80, blank=True)
    automation_level = models.CharField(max_length=24, choices=AutomationLevel.choices, default=AutomationLevel.MANUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_controls")

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_control_tenant_code"),
            models.UniqueConstraint(fields=["code"], condition=Q(tenant__isnull=True), name="uq_control_global_code"),
        ]
        indexes = [models.Index(fields=["tenant", "status"]), models.Index(fields=["tenant", "control_type"])]

    @property
    def is_global(self):
        return self.tenant_id is None

    def clean(self):
        if self.category_id:
            if self.tenant_id is None and self.category.tenant_id is not None:
                raise ValidationError({"category": "A global control cannot use a tenant category."})
            if self.tenant_id is not None and self.category.tenant_id not in {None, self.tenant_id}:
                raise ValidationError({"category": "Control category is not visible to this tenant."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.title}"


class ControlRequirement(UUIDTimeStampedModel):
    class MappingType(models.TextChoices):
        EXACT = "exact", "Exact"
        STRONG = "strong", "Strong"
        PARTIAL = "partial", "Partial"
        RELATED = "related", "Related"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE, related_name="control_requirement_mappings")
    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="requirement_mappings")
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="control_mappings")
    coverage = models.DecimalField(max_digits=5, decimal_places=2, default=100, validators=[MinValueValidator(0), MaxValueValidator(100)])
    mapping_type = models.CharField(max_length=16, choices=MappingType.choices, default=MappingType.RELATED)
    rationale = models.TextField(blank=True)
    source = models.CharField(max_length=24, default="manual")
    approved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "control", "requirement"], name="uq_control_requirement_tenant"),
            models.UniqueConstraint(fields=["control", "requirement"], condition=Q(tenant__isnull=True), name="uq_control_requirement_global"),
        ]
        indexes = [models.Index(fields=["tenant", "control"]), models.Index(fields=["tenant", "requirement"])]


class ControlImplementation(UUIDTimeStampedModel):
    class ImplementationStatus(models.TextChoices):
        NOT_IMPLEMENTED = "not_implemented", "Not implemented"
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        IMPLEMENTED = "implemented", "Implemented"
        SUSPENDED = "suspended", "Suspended"

    class Effectiveness(models.TextChoices):
        NOT_ASSESSED = "not_assessed", "Not assessed"
        INEFFECTIVE = "ineffective", "Ineffective"
        PARTIAL = "partial", "Partially effective"
        EFFECTIVE = "effective", "Effective"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="control_implementations")
    control = models.ForeignKey(Control, on_delete=models.PROTECT, related_name="implementations")
    organization_unit = models.ForeignKey(OrganizationUnit, on_delete=models.PROTECT, related_name="control_implementations")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_control_implementations")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="operated_control_implementations")
    implementation_description = models.TextField(blank=True)
    implementation_status = models.CharField(max_length=24, choices=ImplementationStatus.choices, default=ImplementationStatus.NOT_IMPLEMENTED)
    effectiveness = models.CharField(max_length=24, choices=Effectiveness.choices, default=Effectiveness.NOT_ASSESSED)
    implementation_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "control", "organization_unit"], name="uq_control_implementation_scope")]
        indexes = [models.Index(fields=["tenant", "organization_unit", "implementation_status"]), models.Index(fields=["tenant", "owner"])]

    def __str__(self):
        return f"{self.control.code}@{self.organization_unit.code}"


class ControlTest(UUIDTimeStampedModel):
    class Frequency(models.TextChoices):
        ON_DEMAND="on_demand","On demand"; MONTHLY="monthly","Monthly"; QUARTERLY="quarterly","Quarterly"; SEMIANNUAL="semiannual","Semiannual"; ANNUAL="annual","Annual"
    class AutomationType(models.TextChoices):
        MANUAL="manual","Manual"; SEMI="semi_automated","Semi-automated"; AUTOMATED="automated","Automated"
    control_implementation=models.ForeignKey(ControlImplementation,on_delete=models.CASCADE,related_name="tests")
    title=models.CharField(max_length=255); method=models.TextField(); expected_result=models.TextField(blank=True)
    frequency=models.CharField(max_length=20,choices=Frequency.choices,default=Frequency.ON_DEMAND)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_control_tests")
    automation_type=models.CharField(max_length=24,choices=AutomationType.choices,default=AutomationType.MANUAL)
    connector_key=models.CharField(max_length=120,blank=True); is_active=models.BooleanField(default=True)
    class Meta: indexes=[models.Index(fields=["control_implementation","is_active"])]

class ControlTestRun(UUIDTimeStampedModel):
    class Result(models.TextChoices):
        PASS="pass","Pass"; FAIL="fail","Fail"; PARTIAL="partial","Partial"; NA="not_applicable","Not applicable"; ERROR="error","Error"
    control_test=models.ForeignKey(ControlTest,on_delete=models.CASCADE,related_name="runs")
    executed_at=models.DateTimeField(); executed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="control_test_runs")
    result=models.CharField(max_length=20,choices=Result.choices); result_value=models.JSONField(default=dict,blank=True); conclusion=models.TextField(blank=True); next_test_date=models.DateField(null=True,blank=True)
    class Meta: indexes=[models.Index(fields=["control_test","executed_at"]),models.Index(fields=["result","executed_at"])]

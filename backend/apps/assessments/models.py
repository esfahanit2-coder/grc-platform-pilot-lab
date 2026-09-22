from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.common.models import UUIDTimeStampedModel
from apps.frameworks.models import FrameworkVersion, Requirement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class Assessment(UUIDTimeStampedModel):
    class AssessmentType(models.TextChoices):
        COMPLIANCE = "compliance", "Compliance"
        MATURITY = "maturity", "Maturity"
        INTERNAL = "internal", "Internal assessment"
        SELF = "self", "Self assessment"
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        IN_REVIEW = "in_review", "In review"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="assessments")
    framework_version = models.ForeignKey(FrameworkVersion, on_delete=models.PROTECT, related_name="assessments")
    organization_unit = models.ForeignKey(OrganizationUnit, null=True, blank=True, on_delete=models.PROTECT, related_name="assessments")
    title = models.CharField(max_length=255)
    assessment_type = models.CharField(max_length=24, choices=AssessmentType.choices, default=AssessmentType.COMPLIANCE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_assessments")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    overall_score = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "organization_unit", "status"]),
            models.Index(fields=["tenant", "owner", "due_date"]),
            models.Index(fields=["tenant", "framework_version"]),
        ]

    def __str__(self):
        return self.title


class AssessmentItem(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        NOT_ASSESSED = "not_assessed", "Not assessed"
        COMPLIANT = "compliant", "Compliant"
        PARTIAL = "partial", "Partially compliant"
        NON_COMPLIANT = "non_compliant", "Non-compliant"
        NOT_APPLICABLE = "not_applicable", "Not applicable"
        COMPENSATING = "compensating_control", "Compensating control"
    class Applicability(models.TextChoices):
        APPLICABLE = "applicable", "Applicable"
        NOT_APPLICABLE = "not_applicable", "Not applicable"
        UNDETERMINED = "undetermined", "Undetermined"

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    requirement = models.ForeignKey(Requirement, on_delete=models.PROTECT, related_name="assessment_items")
    requirement_code_snapshot = models.CharField(max_length=160)
    requirement_title_snapshot = models.TextField()
    requirement_body_snapshot = models.TextField(blank=True)
    weight_snapshot = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    status = models.CharField(max_length=28, choices=Status.choices, default=Status.NOT_ASSESSED)
    score = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    maturity_level = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    applicability = models.CharField(max_length=20, choices=Applicability.choices, default=Applicability.UNDETERMINED)
    assessor_comment = models.TextField(blank=True)
    reviewer_comment = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_assessment_items")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_assessment_items")

    class Meta:
        ordering = ["requirement__sort_order", "requirement_code_snapshot"]
        constraints = [models.UniqueConstraint(fields=["assessment", "requirement"], name="uq_assessment_requirement")]
        indexes = [
            models.Index(fields=["assessment", "status"]),
            models.Index(fields=["assessment", "assigned_to"]),
        ]

    def __str__(self):
        return f"{self.assessment_id}:{self.requirement_code_snapshot}"

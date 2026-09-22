from django.conf import settings
from django.db import models

from apps.assessments.models import AssessmentItem
from apps.common.models import UUIDTimeStampedModel
from apps.controls.models import ControlImplementation
from apps.frameworks.models import Requirement
from apps.organizations.models import OrganizationUnit
from apps.risks.models import Risk
from apps.tenancy.models import Tenant
from apps.internal_audits.models import Workpaper


class Finding(UUIDTimeStampedModel):
    class FindingType(models.TextChoices):
        NON_CONFORMITY = "non_conformity", "Non-conformity"
        OBSERVATION = "observation", "Observation"
        WEAKNESS = "weakness", "Weakness"
        OPPORTUNITY = "opportunity", "Opportunity for improvement"
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REMEDIATION = "in_remediation", "In remediation"
        VERIFICATION = "verification", "Verification"
        CLOSED = "closed", "Closed"
        ACCEPTED = "accepted", "Accepted"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="findings")
    organization_unit = models.ForeignKey(OrganizationUnit, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    assessment_item = models.ForeignKey(AssessmentItem, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    audit_workpaper = models.ForeignKey(Workpaper, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    requirement = models.ForeignKey(Requirement, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    control_implementation = models.ForeignKey(ControlImplementation, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    risk = models.ForeignKey(Risk, null=True, blank=True, on_delete=models.PROTECT, related_name="findings")
    finding_type = models.CharField(max_length=24, choices=FindingType.choices, default=FindingType.NON_CONFORMITY)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.MEDIUM)
    root_cause = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_findings")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_findings")
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "organization_unit", "status"]),
            models.Index(fields=["tenant", "owner", "due_date"]),
            models.Index(fields=["tenant", "severity", "status"]),
        ]

    def __str__(self):
        return self.title

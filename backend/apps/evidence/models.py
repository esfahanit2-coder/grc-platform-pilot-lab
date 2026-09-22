from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class Evidence(UUIDTimeStampedModel):
    class EvidenceType(models.TextChoices):
        FILE = "file", "File"
        URL = "url", "URL"
        TEXT = "text", "Text"
        SCREENSHOT = "screenshot", "Screenshot"
        REPORT = "report", "Report"
        LOG = "log", "Log"
        CONFIGURATION = "configuration", "Configuration"
        OTHER = "other", "Other"
    class Classification(models.TextChoices):
        PUBLIC = "public", "Public"
        INTERNAL = "internal", "Internal"
        CONFIDENTIAL = "confidential", "Confidential"
        SECRET = "secret", "Secret"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="evidence")
    organization_unit = models.ForeignKey(OrganizationUnit, null=True, blank=True, on_delete=models.PROTECT, related_name="evidence")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    evidence_type = models.CharField(max_length=24, choices=EvidenceType.choices, default=EvidenceType.FILE)
    source = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_evidence")
    collected_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    classification = models.CharField(max_length=20, choices=Classification.choices, default=Classification.INTERNAL)
    storage_key = models.CharField(max_length=500, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=160, blank=True)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    url = models.URLField(blank=True)
    text_content = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "organization_unit", "classification"]),
            models.Index(fields=["tenant", "owner", "classification"]),
            models.Index(fields=["tenant", "valid_until"]),
            models.Index(fields=["tenant", "sha256"]),
        ]

    def __str__(self):
        return self.title


class EvidenceLink(UUIDTimeStampedModel):
    class RelationType(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        PROVES = "proves", "Proves"
        REFERENCES = "references", "References"
        GENERATED_FROM = "generated_from", "Generated from"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="evidence_links")
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name="links")
    object_type = models.CharField(max_length=60)
    object_id = models.UUIDField()
    relation_type = models.CharField(max_length=24, choices=RelationType.choices, default=RelationType.SUPPORTS)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "evidence", "object_type", "object_id", "relation_type"], name="uq_evidence_object_link")]
        indexes = [models.Index(fields=["tenant", "object_type", "object_id"])]

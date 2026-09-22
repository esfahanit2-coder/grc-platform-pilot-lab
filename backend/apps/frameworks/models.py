from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, F

from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant


class Framework(UUIDTimeStampedModel):
    class FrameworkType(models.TextChoices):
        STANDARD = "standard", "Standard"
        REGULATION = "regulation", "Regulation"
        LAW = "law", "Law"
        MATURITY_MODEL = "maturity_model", "Maturity model"
        INTERNAL_POLICY = "internal_policy", "Internal policy"
        QUESTIONNAIRE = "questionnaire", "Questionnaire"
        BEST_PRACTICE = "best_practice", "Best practice"

    class ContentSource(models.TextChoices):
        BUILT_IN = "built_in", "Built in"
        IMPORTED = "imported", "Imported"
        CUSTOMER = "customer", "Customer provided"
        INTERNAL = "internal", "Internal"

    class LicenseType(models.TextChoices):
        PUBLIC = "public", "Public"
        LICENSED = "licensed", "Licensed"
        CUSTOMER_PROVIDED = "customer_provided", "Customer provided"
        INTERNAL = "internal", "Internal"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE, related_name="frameworks")
    code = models.SlugField(max_length=120)
    name = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255, blank=True)
    framework_type = models.CharField(max_length=32, choices=FrameworkType.choices, default=FrameworkType.STANDARD)
    content_source = models.CharField(max_length=32, choices=ContentSource.choices, default=ContentSource.CUSTOMER)
    license_type = models.CharField(max_length=32, choices=LicenseType.choices, default=LicenseType.CUSTOMER_PROVIDED)
    license_metadata = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_frameworks")

    class Meta:
        ordering = ["name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_framework_tenant_code"),
            models.UniqueConstraint(fields=["code"], condition=Q(tenant__isnull=True), name="uq_framework_global_code"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["code", "status"]),
        ]

    @property
    def is_global(self):
        return self.tenant_id is None

    def __str__(self):
        prefix = "global" if self.tenant_id is None else self.tenant.code
        return f"{prefix}:{self.code}"


class FrameworkVersion(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name="versions")
    version_code = models.CharField(max_length=80)
    title = models.CharField(max_length=255, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    retirement_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    is_locked = models.BooleanField(default=False)
    checksum = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_framework_versions")

    class Meta:
        ordering = ["framework__name", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["framework", "version_code"], name="uq_framework_version_code")]
        indexes = [models.Index(fields=["framework", "status", "is_locked"])]

    def __str__(self):
        return f"{self.framework.code}:{self.version_code}"


class Requirement(UUIDTimeStampedModel):
    framework_version = models.ForeignKey(FrameworkVersion, on_delete=models.CASCADE, related_name="requirements")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    code = models.CharField(max_length=160)
    title = models.TextField()
    body = models.TextField(blank=True)
    guidance = models.TextField(blank=True)
    assessable = models.BooleanField(default=True)
    mandatory = models.BooleanField(default=True)
    weight = models.DecimalField(max_digits=8, decimal_places=3, default=1, validators=[MinValueValidator(0)])
    sort_order = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "code"]
        constraints = [models.UniqueConstraint(fields=["framework_version", "code"], name="uq_requirement_version_code")]
        indexes = [
            models.Index(fields=["framework_version", "parent", "sort_order"]),
            models.Index(fields=["framework_version", "assessable"]),
        ]

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.id:
                raise ValidationError({"parent": "A requirement cannot be its own parent."})
            if self.parent.framework_version_id != self.framework_version_id:
                raise ValidationError({"parent": "Parent requirement must belong to the same framework version."})
            node = self.parent
            visited = set()
            while node is not None and node.id not in visited:
                if self.id and node.id == self.id:
                    raise ValidationError({"parent": "Requirement hierarchy cannot contain cycles."})
                visited.add(node.id)
                node = node.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.framework_version}:{self.code}"


class RequirementTranslation(UUIDTimeStampedModel):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=12)
    title = models.TextField(blank=True)
    body = models.TextField(blank=True)
    guidance = models.TextField(blank=True)

    class Meta:
        ordering = ["language"]
        constraints = [models.UniqueConstraint(fields=["requirement", "language"], name="uq_requirement_translation_language")]


class RequirementMapping(UUIDTimeStampedModel):
    class MappingType(models.TextChoices):
        EXACT = "exact", "Exact"
        STRONG = "strong", "Strong"
        PARTIAL = "partial", "Partial"
        RELATED = "related", "Related"
        WEAK = "weak", "Weak"

    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORTED = "imported", "Imported"
        AI = "ai", "AI"
        VENDOR = "vendor", "Vendor provided"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="requirement_mappings")
    source_requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="outgoing_mappings")
    target_requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="incoming_mappings")
    mapping_type = models.CharField(max_length=16, choices=MappingType.choices, default=MappingType.RELATED)
    strength = models.DecimalField(max_digits=5, decimal_places=4, default=0.5, validators=[MinValueValidator(0), MaxValueValidator(1)])
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])
    source_type = models.CharField(max_length=16, choices=SourceType.choices, default=SourceType.MANUAL)
    rationale = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_requirement_mappings")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["source_requirement__code", "target_requirement__code"]
        constraints = [
            models.CheckConstraint(condition=~Q(source_requirement=F("target_requirement")), name="ck_mapping_source_not_target"),
            models.UniqueConstraint(fields=["tenant", "source_requirement", "target_requirement"], name="uq_tenant_requirement_mapping"),
        ]
        indexes = [
            models.Index(fields=["tenant", "mapping_type"]),
            models.Index(fields=["tenant", "source_type"]),
        ]

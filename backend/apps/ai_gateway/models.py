from django.conf import settings
from django.db import models
from pgvector.django import VectorField
from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class AIProviderConfig(UUIDTimeStampedModel):
    class ProviderType(models.TextChoices):
        OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible"
        OLLAMA = "ollama", "Ollama"
        VLLM = "vllm", "vLLM"
        PRIVATE = "private", "Private endpoint"
        MOCK = "mock", "Mock/Test"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ai_provider_configs")
    name = models.CharField(max_length=120)
    provider_type = models.CharField(max_length=32, choices=ProviderType.choices)
    base_url = models.URLField(max_length=500, blank=True)
    model_name = models.CharField(max_length=160)
    secret_env_var = models.CharField(max_length=120, blank=True, help_text="Environment variable containing the provider API key. Secrets are never persisted here.")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    allow_confidential = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="uq_ai_provider_tenant_name")]
        indexes = [models.Index(fields=["tenant", "is_active", "is_default"])]

    def __str__(self):
        return f"{self.name} ({self.model_name})"


class AIInteraction(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ai_interactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_interactions")
    provider = models.ForeignKey(AIProviderConfig, null=True, blank=True, on_delete=models.SET_NULL, related_name="interactions")
    capability = models.CharField(max_length=80)
    classification = models.CharField(max_length=24, default="internal")
    input_summary = models.TextField(blank=True)
    context_manifest = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "capability", "created_at"]), models.Index(fields=["tenant", "status"])]


class AISuggestion(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        MODIFIED = "modified", "Modified"
        REJECTED = "rejected", "Rejected"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ai_suggestions")
    interaction = models.ForeignKey(AIInteraction, on_delete=models.CASCADE, related_name="suggestions")
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    suggestion_type = models.CharField(max_length=80)
    proposed_value = models.JSONField(default=dict)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_ai_suggestions")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status", "created_at"]), models.Index(fields=["tenant", "object_type", "object_id"])]


class KnowledgeChunk(UUIDTimeStampedModel):
    """Tenant-scoped RAG chunk supporting lexical and pgvector semantic retrieval."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="knowledge_chunks")
    organization_unit = models.ForeignKey(OrganizationUnit, null=True, blank=True, on_delete=models.PROTECT, related_name="knowledge_chunks")
    source_type = models.CharField(max_length=60)
    source_id = models.UUIDField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)
    token_count = models.PositiveIntegerField(default=0)
    classification = models.CharField(max_length=24, default="internal")
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(null=True, blank=True)
    embedding_model = models.CharField(max_length=160, blank=True)
    embedding_dimensions = models.PositiveIntegerField(default=0)
    embedded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "content_hash"], name="uq_knowledge_chunk_tenant_hash")]
        indexes = [models.Index(fields=["tenant", "source_type", "source_id"]), models.Index(fields=["tenant", "organization_unit"])]

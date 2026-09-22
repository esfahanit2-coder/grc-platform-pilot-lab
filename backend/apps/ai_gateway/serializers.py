import re
from urllib.parse import urlsplit

from rest_framework import serializers

from .models import AIProviderConfig, AIInteraction, AISuggestion, KnowledgeChunk


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SENSITIVE_CONFIG_TOKENS = ("password", "secret", "token", "api_key", "apikey", "credential", "authorization")


def _contains_sensitive_config_key(value):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_").replace(" ", "_")
            if any(token in normalized for token in _SENSITIVE_CONFIG_TOKENS):
                return True
            if _contains_sensitive_config_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_config_key(item) for item in value)
    return False


class AIProviderConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIProviderConfig
        fields = ["id","name","provider_type","base_url","model_name","secret_env_var","is_active","is_default","allow_confidential","configuration","created_at","updated_at"]
        read_only_fields = ["id","created_at","updated_at"]

    def validate_base_url(self, value):
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.username or parsed.password:
            raise serializers.ValidationError("Provider URL must not contain embedded credentials.")
        if parsed.query or parsed.fragment:
            raise serializers.ValidationError("Provider base URL must not contain query parameters or fragments.")
        return value

    def validate_secret_env_var(self, value):
        value = str(value or "").strip()
        if value and not _ENV_NAME.fullmatch(value):
            raise serializers.ValidationError("Use an environment-variable name, not a literal secret value.")
        return value

    def validate_configuration(self, value):
        if _contains_sensitive_config_key(value):
            raise serializers.ValidationError(
                "Provider configuration must not contain credentials or secret-like keys; use secret_env_var."
            )
        return value


class AIInteractionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    class Meta:
        model = AIInteraction
        fields = ["id","capability","classification","provider","provider_name","input_summary","context_manifest","output","confidence","status","error","created_at"]
        read_only_fields = fields


class AISuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISuggestion
        fields = ["id","interaction","object_type","object_id","suggestion_type","proposed_value","confidence","status","reviewed_by","reviewed_at","review_comment","created_at"]
        read_only_fields = fields


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeChunk
        fields = ["id","organization_unit","source_type","source_id","title","content","content_hash","token_count","classification","metadata","embedding_model","embedding_dimensions","embedded_at","created_at","updated_at"]
        read_only_fields = ["id","content_hash","token_count","embedding_model","embedding_dimensions","embedded_at","created_at","updated_at"]

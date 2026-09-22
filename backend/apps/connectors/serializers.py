import urllib.parse

from django.conf import settings
from rest_framework import serializers

from .clients import FORTIGATE_COLLECTION_PROFILES, validate_secret_env_name
from .models import ConnectorConfig, ConnectorRun


class ConnectorConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectorConfig
        fields = [
            "id",
            "organization_unit",
            "name",
            "connector_type",
            "base_url",
            "username_env_var",
            "secret_env_var",
            "secondary_secret_env_var",
            "verify_tls",
            "is_active",
            "configuration",
            "last_sync_at",
            "last_status",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_sync_at", "last_status", "last_error", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = self.instance
        connector_type = attrs.get("connector_type") or getattr(instance, "connector_type", None)
        base_url = attrs.get("base_url", getattr(instance, "base_url", ""))
        configuration = attrs.get("configuration", getattr(instance, "configuration", {}) or {}) or {}
        verify_tls = attrs.get("verify_tls", getattr(instance, "verify_tls", True))

        if not isinstance(configuration, dict):
            raise serializers.ValidationError({"configuration": "Connector configuration must be an object."})

        for field in ("username_env_var", "secret_env_var", "secondary_secret_env_var"):
            value = attrs.get(field, getattr(instance, field, ""))
            try:
                validate_secret_env_name(value)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({field: exc.detail}) from exc

        if connector_type in {
            ConnectorConfig.ConnectorType.FORTIGATE,
            ConnectorConfig.ConnectorType.TENABLE,
            ConnectorConfig.ConnectorType.VEEAM,
        }:
            parsed = urllib.parse.urlparse(str(base_url or "").strip())
            if parsed.scheme not in {"https", "http"} or not parsed.hostname:
                raise serializers.ValidationError({"base_url": "HTTP connectors require an http(s) base_url with a hostname."})
            if parsed.username or parsed.password:
                raise serializers.ValidationError({"base_url": "Credentials must not be embedded in base_url."})
            if parsed.query or parsed.fragment:
                raise serializers.ValidationError({"base_url": "base_url must not contain a query string or fragment."})

        if connector_type == ConnectorConfig.ConnectorType.FORTIGATE:
            profile = configuration.get("collection_profile") or "baseline"
            if profile not in FORTIGATE_COLLECTION_PROFILES:
                raise serializers.ValidationError(
                    {"configuration": f"FortiGate collection_profile must be one of {sorted(FORTIGATE_COLLECTION_PROFILES)}."}
                )
            paths = configuration.get("read_paths") or []
            if not isinstance(paths, list):
                raise serializers.ValidationError({"configuration": "FortiGate read_paths must be a list."})
            if len(paths) > 10:
                raise serializers.ValidationError({"configuration": "At most 10 FortiGate read paths are allowed."})
            if any(not isinstance(path, str) or not path.startswith("/api/v2/") for path in paths):
                raise serializers.ValidationError({"configuration": "FortiGate read_paths must stay under /api/v2/."})

        if connector_type == ConnectorConfig.ConnectorType.ACTIVE_DIRECTORY:
            if not (configuration.get("host") or base_url):
                raise serializers.ValidationError({"configuration": "AD connector requires configuration.host or base_url."})
            if not configuration.get("base_dn"):
                raise serializers.ValidationError({"configuration": "AD connector requires configuration.base_dn."})
            try:
                size_limit = int(configuration.get("size_limit", 5000))
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError({"configuration": "AD size_limit must be an integer."}) from exc
            if size_limit < 1 or size_limit > 10000:
                raise serializers.ValidationError({"configuration": "AD size_limit must be between 1 and 10000."})
            privileged_groups = configuration.get("privileged_groups") or []
            if not isinstance(privileged_groups, list) or len(privileged_groups) > 50:
                raise serializers.ValidationError({"configuration": "AD privileged_groups must be a list of at most 50 group names or DNs."})
            if "include_sample" in configuration and not isinstance(configuration.get("include_sample"), bool):
                raise serializers.ValidationError({"configuration": "AD include_sample must be boolean."})

        if not verify_tls and getattr(settings, "APP_ENV", "development") == "production":
            raise serializers.ValidationError({"verify_tls": "TLS verification cannot be disabled in production."})
        return attrs


class ConnectorRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectorRun
        fields = ["id", "connector", "triggered_by", "status", "started_at", "finished_at", "summary", "error"]
        read_only_fields = fields

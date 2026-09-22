from rest_framework import serializers

from apps.tenancy.models import TenantMembership

from .malware import SERVER_MANAGED_MALWARE_METADATA_KEYS
from .models import Evidence, EvidenceLink
from .services import link_scope


class EvidenceSerializer(serializers.ModelSerializer):
    owner_display = serializers.SerializerMethodField()
    links_count = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization_unit.name", read_only=True)

    class Meta:
        model = Evidence
        fields = [
            "id", "organization_unit", "organization_name", "title", "description", "evidence_type", "source",
            "owner", "owner_display", "collected_at", "valid_until", "classification", "storage_key",
            "original_filename", "mime_type", "size", "sha256", "url", "text_content", "metadata",
            "links_count", "created_at", "updated_at",
        ]
        read_only_fields = ["storage_key", "original_filename", "mime_type", "size", "sha256", "links_count", "created_at", "updated_at"]

    def get_owner_display(self, obj):
        return obj.owner.get_full_name() or obj.owner.get_username()

    def get_links_count(self, obj):
        return obj.links.filter(deleted_at__isnull=True).count()

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Evidence metadata must be an object.")
        forbidden = sorted(SERVER_MANAGED_MALWARE_METADATA_KEYS.intersection(value.keys()))
        if forbidden:
            raise serializers.ValidationError(
                "Malware scan metadata is server-managed and cannot be supplied by API clients."
            )
        if self.instance:
            # A normal metadata edit must not erase or overwrite quarantine state.
            existing = dict(self.instance.metadata or {})
            merged = dict(value)
            for key in SERVER_MANAGED_MALWARE_METADATA_KEYS:
                if key in existing:
                    merged[key] = existing[key]
            return merged
        return value

    def validate(self, attrs):
        tenant = self.context["tenant"]
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if owner and not TenantMembership.objects.filter(tenant=tenant, user=owner, is_active=True).exists():
            raise serializers.ValidationError({"owner": "Owner must be an active tenant member."})
        unit = attrs.get("organization_unit", getattr(self.instance, "organization_unit", None))
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Organization unit must belong to tenant."})
        return attrs


class EvidenceLinkSerializer(serializers.ModelSerializer):
    evidence_title = serializers.CharField(source="evidence.title", read_only=True)

    class Meta:
        model = EvidenceLink
        fields = ["id", "evidence", "evidence_title", "object_type", "object_id", "relation_type", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        tenant = self.context["tenant"]
        evidence = attrs.get("evidence", getattr(self.instance, "evidence", None))
        if evidence and evidence.tenant_id != tenant.id:
            raise serializers.ValidationError({"evidence": "Evidence must belong to tenant."})
        object_type = attrs.get("object_type", getattr(self.instance, "object_type", None))
        object_id = attrs.get("object_id", getattr(self.instance, "object_id", None))
        obj, _ = link_scope(tenant, object_type, object_id)
        if obj is None:
            raise serializers.ValidationError({"object_id": "Evidence target does not exist in this tenant/context."})
        return attrs

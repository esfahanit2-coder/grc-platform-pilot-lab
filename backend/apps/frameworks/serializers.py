from django.db import transaction
from rest_framework import serializers

from .models import Framework, FrameworkVersion, Requirement, RequirementMapping, RequirementTranslation
from .services import require_editable_version, require_local_framework, validate_mapping_access, visible_frameworks


class FrameworkSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(read_only=True)
    versions_count = serializers.SerializerMethodField()

    class Meta:
        model = Framework
        fields = [
            "id", "code", "name", "publisher", "framework_type", "content_source", "license_type",
            "license_metadata", "description", "status", "is_global", "versions_count", "created_at", "updated_at",
        ]
        read_only_fields = ["content_source", "created_at", "updated_at"]

    def get_versions_count(self, obj):
        return obj.versions.filter(deleted_at__isnull=True, status="active").count() if obj.is_global else obj.versions.filter(deleted_at__isnull=True).count()


class FrameworkVersionSerializer(serializers.ModelSerializer):
    framework_code = serializers.CharField(source="framework.code", read_only=True)
    framework_name = serializers.CharField(source="framework.name", read_only=True)
    requirement_count = serializers.SerializerMethodField()

    class Meta:
        model = FrameworkVersion
        fields = [
            "id", "framework", "framework_code", "framework_name", "version_code", "title",
            "publication_date", "effective_date", "retirement_date", "status", "is_locked", "checksum",
            "metadata", "requirement_count", "created_at", "updated_at",
        ]
        read_only_fields = ["is_locked", "checksum", "created_at", "updated_at"]

    def get_requirement_count(self, obj):
        return obj.requirements.filter(deleted_at__isnull=True).count()

    def validate_framework(self, framework):
        tenant = self.context["tenant"]
        if framework.tenant_id != tenant.id:
            raise serializers.ValidationError("Versions can only be created under tenant-owned frameworks.")
        return framework

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            require_editable_version(instance, self.context["tenant"])
            if "framework" in attrs and attrs["framework"].id != instance.framework_id:
                raise serializers.ValidationError({"framework": "A framework version cannot be moved to another framework."})
        return attrs


class RequirementTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementTranslation
        fields = ["id", "language", "title", "body", "guidance"]
        read_only_fields = ["id"]


class RequirementSerializer(serializers.ModelSerializer):
    translations = RequirementTranslationSerializer(many=True, required=False)
    parent_code = serializers.CharField(source="parent.code", read_only=True)
    version_code = serializers.CharField(source="framework_version.version_code", read_only=True)
    framework_code = serializers.CharField(source="framework_version.framework.code", read_only=True)

    class Meta:
        model = Requirement
        fields = [
            "id", "framework_version", "framework_code", "version_code", "parent", "parent_code", "code", "title",
            "body", "guidance", "assessable", "mandatory", "weight", "sort_order", "metadata", "translations",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_framework_version(self, version):
        require_editable_version(version, self.context["tenant"])
        return version

    def validate(self, attrs):
        tenant = self.context["tenant"]
        version = attrs.get("framework_version") or getattr(self.instance, "framework_version", None)
        if version is None:
            raise serializers.ValidationError({"framework_version": "Framework version is required."})
        if self.instance is not None and "framework_version" in attrs and attrs["framework_version"].id != self.instance.framework_version_id:
            raise serializers.ValidationError({"framework_version": "A requirement cannot be moved to another framework version."})
        require_editable_version(version, tenant)
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent and parent.framework_version_id != version.id:
            raise serializers.ValidationError({"parent": "Parent must belong to the same framework version."})
        return attrs

    def _save_translations(self, requirement, translations):
        if translations is None:
            return
        existing = {tr.language: tr for tr in requirement.translations.all()}
        sent = set()
        for data in translations:
            language = data["language"]
            sent.add(language)
            item = existing.get(language)
            if item:
                for key in ("title", "body", "guidance"):
                    setattr(item, key, data.get(key, ""))
                item.save()
            else:
                RequirementTranslation.objects.create(requirement=requirement, **data)
        requirement.translations.exclude(language__in=sent).delete()

    @transaction.atomic
    def create(self, validated_data):
        translations = validated_data.pop("translations", [])
        requirement = Requirement.objects.create(**validated_data)
        self._save_translations(requirement, translations)
        return requirement

    @transaction.atomic
    def update(self, instance, validated_data):
        translations = validated_data.pop("translations", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        self._save_translations(instance, translations)
        return instance


class RequirementMappingSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source_requirement.code", read_only=True)
    target_code = serializers.CharField(source="target_requirement.code", read_only=True)
    source_framework = serializers.CharField(source="source_requirement.framework_version.framework.code", read_only=True)
    target_framework = serializers.CharField(source="target_requirement.framework_version.framework.code", read_only=True)

    class Meta:
        model = RequirementMapping
        fields = [
            "id", "source_requirement", "source_code", "source_framework", "target_requirement", "target_code",
            "target_framework", "mapping_type", "strength", "confidence", "source_type", "rationale",
            "reviewed_by", "approved_at", "created_at", "updated_at",
        ]
        read_only_fields = ["reviewed_by", "approved_at", "created_at", "updated_at"]

    def validate(self, attrs):
        source = attrs.get("source_requirement") or getattr(self.instance, "source_requirement", None)
        target = attrs.get("target_requirement") or getattr(self.instance, "target_requirement", None)
        if source is None or target is None:
            return attrs
        if source.id == target.id:
            raise serializers.ValidationError("A requirement cannot be mapped to itself.")
        validate_mapping_access(source, target, self.context["tenant"])
        return attrs

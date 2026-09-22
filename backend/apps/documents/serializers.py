from rest_framework import serializers

from apps.identity.services import has_tenant_permission, has_whole_tenant_permission
from apps.tenancy.models import TenantMembership

from .models import Document, DocumentApproval, DocumentLink, DocumentVersion, ReportTemplate


def _has_scoped_permission(user, tenant, permission_code, organization_unit):
    if organization_unit is None:
        return has_whole_tenant_permission(user, tenant, permission_code)
    return has_tenant_permission(user, tenant, permission_code, organization_unit)


class DocumentSerializer(serializers.ModelSerializer):
    owner_display = serializers.SerializerMethodField()
    current_version_code = serializers.CharField(source="current_version.version", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "organization_unit",
            "document_type",
            "code",
            "title",
            "owner",
            "owner_display",
            "status",
            "review_date",
            "current_version",
            "current_version_code",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "current_version", "created_at", "updated_at"]

    def get_owner_display(self, document):
        return document.owner.get_full_name() or document.owner.get_username()

    def validate(self, attrs):
        tenant = self.context["tenant"]
        unit = attrs.get("organization_unit", getattr(self.instance, "organization_unit", None))
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if unit and unit.tenant_id != tenant.id:
            raise serializers.ValidationError({"organization_unit": "Unit must belong to tenant."})
        if owner:
            if not TenantMembership.objects.filter(tenant=tenant, user=owner, is_active=True).exists():
                raise serializers.ValidationError({"owner": "Owner must be an active tenant member."})
            if not _has_scoped_permission(owner, tenant, "document.view", unit):
                raise serializers.ValidationError(
                    {"owner": "Owner must have document.view permission in the selected document scope."}
                )
        return attrs


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "version",
            "content",
            "storage_key",
            "change_summary",
            "created_by",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "status", "created_at", "updated_at"]

    def validate_document(self, document):
        if document.tenant_id != self.context["tenant"].id:
            raise serializers.ValidationError("Document must belong to tenant.")
        if self.instance is not None and document.id != self.instance.document_id:
            raise serializers.ValidationError("Document version cannot be moved to another document.")
        return document


class DocumentApprovalSerializer(serializers.ModelSerializer):
    approver_display = serializers.SerializerMethodField()
    can_decide = serializers.SerializerMethodField()

    class Meta:
        model = DocumentApproval
        fields = [
            "id",
            "version",
            "approver",
            "approver_display",
            "approval_order",
            "decision",
            "comment",
            "decided_at",
            "created_at",
            "can_decide",
        ]
        read_only_fields = ["decision", "comment", "decided_at", "created_at", "can_decide"]
        # Reactivation of a previously removed pending assignment is handled
        # explicitly in create(); the database constraint remains authoritative.
        validators = []

    def get_approver_display(self, approval):
        return approval.approver.get_full_name() or approval.approver.get_username()

    def get_can_decide(self, approval):
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if not request or not tenant or not getattr(request.user, "is_authenticated", False):
            return False
        if approval.deleted_at is not None:
            return False
        if approval.decision != DocumentApproval.Decision.PENDING:
            return False
        if approval.version.status != DocumentVersion.Status.REVIEW:
            return False
        if approval.approver_id != request.user.id:
            return False
        return _has_scoped_permission(
            request.user,
            tenant,
            "document.approve",
            approval.version.document.organization_unit,
        )

    def validate_version(self, version):
        tenant = self.context["tenant"]
        if version.document.tenant_id != tenant.id or version.document.deleted_at is not None:
            raise serializers.ValidationError("Document version must belong to the selected tenant.")
        if self.instance is not None and version.id != self.instance.version_id:
            raise serializers.ValidationError("Approval cannot be moved to another version.")
        return version

    def validate(self, attrs):
        tenant = self.context["tenant"]
        version = attrs.get("version", getattr(self.instance, "version", None))
        approver = attrs.get("approver", getattr(self.instance, "approver", None))
        if self.instance is not None and approver and approver.id != self.instance.approver_id:
            raise serializers.ValidationError({"approver": "Approver cannot be changed; remove the pending assignment instead."})
        if version and approver:
            if not TenantMembership.objects.filter(tenant=tenant, user=approver, is_active=True).exists():
                raise serializers.ValidationError({"approver": "Approver must be an active tenant member."})
            if not _has_scoped_permission(approver, tenant, "document.view", version.document.organization_unit):
                raise serializers.ValidationError(
                    {"approver": "Approver must have document.view permission in this document scope."}
                )
            if not _has_scoped_permission(approver, tenant, "document.approve", version.document.organization_unit):
                raise serializers.ValidationError(
                    {"approver": "Approver must have document.approve permission in this document scope."}
                )
        return attrs

    def create(self, validated_data):
        version = validated_data["version"]
        approver = validated_data["approver"]
        existing = DocumentApproval.objects.filter(version=version, approver=approver).first()
        if existing:
            if existing.deleted_at is None:
                raise serializers.ValidationError("This approver is already assigned to the version.")
            if existing.decision != DocumentApproval.Decision.PENDING:
                raise serializers.ValidationError("A decided approval assignment cannot be reactivated.")
            existing.deleted_at = None
            existing.approval_order = validated_data.get("approval_order", existing.approval_order)
            existing.save(update_fields=["deleted_at", "approval_order", "updated_at"])
            return existing
        return super().create(validated_data)


class DocumentLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentLink
        fields = "__all__"
        read_only_fields = ["tenant", "created_at", "updated_at", "deleted_at"]


class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = "__all__"
        read_only_fields = ["tenant", "created_at", "updated_at", "deleted_at"]

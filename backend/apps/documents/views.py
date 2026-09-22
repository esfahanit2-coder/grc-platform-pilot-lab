from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.assessments.models import Assessment
from apps.audit.services import record_audit_event
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_tenant_permission,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.organizations.models import OrganizationUnit
from apps.notifications.models import Notification
from apps.notifications.services import notify_user
from apps.tenancy.models import TenantMembership
from apps.tenancy.services import resolve_tenant_for_request

from .exporters import document_docx, soa_docx
from .models import Document, DocumentApproval, DocumentLink, DocumentVersion, ReportTemplate
from .serializers import (
    DocumentApprovalSerializer,
    DocumentLinkSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
    ReportTemplateSerializer,
)


def _has_scoped_permission(user, tenant, permission_code, unit):
    if unit is None:
        return has_whole_tenant_permission(user, tenant, permission_code)
    return has_tenant_permission(user, tenant, permission_code, unit)


def _require_scoped_permission(user, tenant, permission_code, unit):
    if unit is None:
        return require_whole_tenant_permission(user, tenant, permission_code)
    return require_tenant_permission(user, tenant, permission_code, unit)


def _notify_next_document_approvers(version):
    pending = version.approvals.filter(
        deleted_at__isnull=True,
        decision=DocumentApproval.Decision.PENDING,
    ).select_related("approver", "version__document")
    first = pending.order_by("approval_order", "created_at").first()
    if not first:
        return 0
    stage = first.approval_order
    recipients = list(pending.filter(approval_order=stage))
    for approval in recipients:
        already_notified = Notification.objects.filter(
            tenant=version.document.tenant,
            user=approval.approver,
            category="approval_required",
            object_type="document_approval",
            object_id=approval.id,
            deleted_at__isnull=True,
        ).exists()
        if already_notified:
            continue
        notify_user(
            tenant=version.document.tenant,
            user=approval.approver,
            category="approval_required",
            title=f"سند نیازمند تأیید شماست: {version.document.title}",
            body=f"نسخه {version.version} — مرحله تأیید {approval.approval_order}",
            object_type="document_approval",
            object_id=approval.id,
            severity="warning",
        )
    return len(recipients)


def _document_status_for_version(version):
    if version is None:
        return Document.Status.DRAFT
    return {
        DocumentVersion.Status.REVIEW: Document.Status.REVIEW,
        DocumentVersion.Status.APPROVED: Document.Status.APPROVED,
        DocumentVersion.Status.PUBLISHED: Document.Status.PUBLISHED,
    }.get(version.status, Document.Status.DRAFT)


def _lock_document(tenant, document_id):
    document = (
        Document.objects.select_for_update(of=("self",))
        .select_related("organization_unit", "current_version")
        .filter(id=document_id, tenant=tenant, deleted_at__isnull=True)
        .first()
    )
    if not document:
        raise ValidationError("Document not found.")
    return document


def _lock_document_version(tenant, version_id):
    candidate = (
        DocumentVersion.objects.filter(
            id=version_id,
            document__tenant=tenant,
            deleted_at__isnull=True,
        )
        .values("document_id")
        .first()
    )
    if not candidate:
        raise ValidationError("Document version not found.")

    document = _lock_document(tenant, candidate["document_id"])
    version = (
        DocumentVersion.objects.select_for_update(of=("self",))
        .select_related("created_by")
        .filter(
            id=version_id,
            document=document,
            deleted_at__isnull=True,
        )
        .first()
    )
    if not version:
        raise ValidationError("Document version not found.")
    # Reuse the locked aggregate root for downstream scope/status checks.
    version.document = document
    return document, version


class TM:
    def _tenant(self):
        if not hasattr(self, "_t"):
            self._t = resolve_tenant_for_request(self.request)
        return self._t

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self._tenant()
        return context


class DocumentViewSet(TM, viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "document.view")
        queryset = Document.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
        ).select_related("organization_unit", "owner", "current_version")
        if not has_whole_tenant_permission(self.request.user, tenant, "document.view"):
            queryset = queryset.filter(
                organization_unit_id__in=accessible_organization_unit_ids(
                    self.request.user, tenant, "document.view"
                )
            )
        return queryset.order_by("code")

    def perform_create(self, serializer):
        tenant = self._tenant()
        unit = serializer.validated_data.get("organization_unit")
        _require_scoped_permission(self.request.user, tenant, "document.manage", unit)
        document = serializer.save(tenant=tenant)
        record_audit_event(
            self.request.user,
            tenant,
            "document.create",
            "document",
            document.id,
            new_data={"code": document.code, "title": document.title},
            request=self.request,
        )

    def perform_update(self, serializer):
        tenant = self._tenant()
        document = serializer.instance
        _require_scoped_permission(
            self.request.user, tenant, "document.manage", document.organization_unit
        )
        new_unit = serializer.validated_data.get("organization_unit", document.organization_unit)
        _require_scoped_permission(self.request.user, tenant, "document.manage", new_unit)
        if new_unit != document.organization_unit and document.current_version_id:
            active_approvals = document.current_version.approvals.filter(deleted_at__isnull=True).exists()
            if document.current_version.status != DocumentVersion.Status.DRAFT or active_approvals:
                raise ValidationError(
                    {"organization_unit": "Document scope cannot change after review governance has started."}
                )
        serializer.save()

    def perform_destroy(self, document):
        tenant = self._tenant()
        _require_scoped_permission(
            self.request.user, tenant, "document.manage", document.organization_unit
        )
        if document.current_version_id and document.current_version.status == DocumentVersion.Status.REVIEW:
            raise ValidationError("A document in review cannot be archived.")
        document.deleted_at = timezone.now()
        document.status = Document.Status.DEPRECATED
        document.save(update_fields=["deleted_at", "status", "updated_at"])
        record_audit_event(
            self.request.user,
            tenant,
            "document.archive",
            "document",
            document.id,
            request=self.request,
        )

    @action(detail=False, methods=["get"], url_path="workspace-options")
    def workspace_options(self, request):
        tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "document.view")
        whole_tenant = has_whole_tenant_permission(request.user, tenant, "document.manage")
        ids = accessible_organization_unit_ids(request.user, tenant, "document.manage")
        units = list(
            OrganizationUnit.objects.for_tenant(tenant)
            .filter(id__in=ids, deleted_at__isnull=True)
            .order_by("name")
            .values("id", "code", "name", "unit_type")
        )
        return Response(
            {
                "tenant_scope_allowed": whole_tenant,
                "units": units,
            }
        )

    @action(detail=False, methods=["get"], url_path="participants")
    def participants(self, request):
        tenant = self._tenant()
        unit_id = request.query_params.get("organization_unit")
        unit = None
        if unit_id:
            unit = (
                OrganizationUnit.objects.for_tenant(tenant)
                .filter(id=unit_id, deleted_at__isnull=True)
                .first()
            )
            if not unit:
                raise ValidationError({"organization_unit": "Organization unit not found."})
        _require_scoped_permission(request.user, tenant, "document.manage", unit)

        kind = str(request.query_params.get("kind", "owner")).strip().lower()
        if kind not in {"owner", "approver"}:
            raise ValidationError({"kind": "Expected owner or approver."})

        memberships = list(
            TenantMembership.objects.filter(tenant=tenant, is_active=True)
            .select_related("user")
            .order_by("user__username")[:501]
        )
        truncated = len(memberships) > 500
        results = []
        for membership in memberships[:500]:
            user = membership.user
            if not _has_scoped_permission(user, tenant, "document.view", unit):
                continue
            if kind == "approver" and not _has_scoped_permission(
                user, tenant, "document.approve", unit
            ):
                continue
            results.append(
                {
                    "id": user.id,
                    "username": user.get_username(),
                    "display": user.get_full_name() or user.get_username(),
                }
            )
        return Response({"results": results, "truncated": truncated})


class DocumentVersionViewSet(TM, viewsets.ModelViewSet):
    serializer_class = DocumentVersionSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "document.view")
        queryset = DocumentVersion.objects.filter(
            document__tenant=tenant,
            deleted_at__isnull=True,
        ).select_related("document__organization_unit", "created_by")
        if not has_whole_tenant_permission(self.request.user, tenant, "document.view"):
            queryset = queryset.filter(
                document__organization_unit_id__in=accessible_organization_unit_ids(
                    self.request.user, tenant, "document.view"
                )
            )
        document_id = self.request.query_params.get("document")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        return queryset.order_by("-created_at")

    def _require_manage(self, version):
        _require_scoped_permission(
            self.request.user,
            self._tenant(),
            "document.manage",
            version.document.organization_unit,
        )

    def _require_mutable_current_draft(self, version):
        self._require_manage(version)
        if version.status != DocumentVersion.Status.DRAFT:
            raise ValidationError("Only a draft version can be modified.")
        if version.document.current_version_id != version.id:
            raise ValidationError("Only the current draft version can be modified.")

    def perform_create(self, serializer):
        tenant = self._tenant()
        candidate = serializer.validated_data["document"]
        with transaction.atomic():
            document = _lock_document(tenant, candidate.id)
            _require_scoped_permission(
                self.request.user, tenant, "document.manage", document.organization_unit
            )
            if (
                document.current_version_id
                and document.current_version.status == DocumentVersion.Status.REVIEW
            ):
                raise ValidationError("The current document version is still in review.")
            version = serializer.save(document=document, created_by=self.request.user)
            document.current_version = version
            document.status = Document.Status.DRAFT
            document.save(update_fields=["current_version", "status", "updated_at"])
            record_audit_event(
                self.request.user,
                tenant,
                "document.version_create",
                "document_version",
                version.id,
                metadata={"document_id": str(document.id), "version": version.version},
                request=self.request,
            )

    def perform_update(self, serializer):
        tenant = self._tenant()
        candidate = serializer.instance
        with transaction.atomic():
            _document, version = _lock_document_version(tenant, candidate.id)
            serializer.instance = version
            self._require_mutable_current_draft(version)
            serializer.save()
            record_audit_event(
                self.request.user,
                tenant,
                "document.version_update",
                "document_version",
                version.id,
                request=self.request,
            )

    def perform_destroy(self, candidate):
        tenant = self._tenant()
        with transaction.atomic():
            document, version = _lock_document_version(tenant, candidate.id)
            self._require_mutable_current_draft(version)
            version.deleted_at = timezone.now()
            version.save(update_fields=["deleted_at", "updated_at"])
            previous = (
                DocumentVersion.objects.filter(document=document, deleted_at__isnull=True)
                .exclude(pk=version.pk)
                .order_by("-created_at")
                .first()
            )
            document.current_version = previous
            document.status = _document_status_for_version(previous)
            document.save(update_fields=["current_version", "status", "updated_at"])
            record_audit_event(
                self.request.user,
                tenant,
                "document.version_remove",
                "document_version",
                version.id,
                request=self.request,
            )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        candidate = self.get_object()
        tenant = self._tenant()
        with transaction.atomic():
            document, version = _lock_document_version(tenant, candidate.id)
            self._require_mutable_current_draft(version)
            approvals = list(
                version.approvals.filter(deleted_at__isnull=True)
                .select_related("approver")
                .order_by("approval_order", "created_at")
            )
            if not approvals:
                raise ValidationError("At least one approver must be assigned before review.")
            if any(item.decision != DocumentApproval.Decision.PENDING for item in approvals):
                raise ValidationError("Review can start only with pending approval assignments.")
            for approval in approvals:
                active_member = TenantMembership.objects.filter(
                    tenant=tenant, user=approval.approver, is_active=True
                ).exists()
                if not active_member or not _has_scoped_permission(
                    approval.approver,
                    tenant,
                    "document.view",
                    document.organization_unit,
                ) or not _has_scoped_permission(
                    approval.approver,
                    tenant,
                    "document.approve",
                    document.organization_unit,
                ):
                    raise ValidationError(
                        "Every approver must still be an active member with document.view and document.approve in this scope."
                    )

            version.status = DocumentVersion.Status.REVIEW
            version.save(update_fields=["status", "updated_at"])
            document.status = Document.Status.REVIEW
            document.save(update_fields=["status", "updated_at"])
            record_audit_event(
                request.user,
                tenant,
                "document.submit_review",
                "document_version",
                version.id,
                metadata={"document_id": str(document.id)},
                request=request,
            )
            _notify_next_document_approvers(version)
            response_data = self.get_serializer(version).data
        return Response(response_data)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        version = self.get_object()
        tenant = self._tenant()
        record_audit_event(
            request.user,
            tenant,
            "document.export",
            "document_version",
            version.id,
            metadata={"document_id": str(version.document_id), "format": "docx"},
            request=request,
        )
        return document_docx(version)


class DocumentApprovalViewSet(TM, viewsets.ModelViewSet):
    serializer_class = DocumentApprovalSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "document.view")
        queryset = DocumentApproval.objects.filter(
            version__document__tenant=tenant,
            deleted_at__isnull=True,
        ).select_related("version__document__organization_unit", "approver")
        if not has_whole_tenant_permission(self.request.user, tenant, "document.view"):
            queryset = queryset.filter(
                version__document__organization_unit_id__in=accessible_organization_unit_ids(
                    self.request.user, tenant, "document.view"
                )
            )
        version_id = self.request.query_params.get("version")
        if version_id:
            queryset = queryset.filter(version_id=version_id)
        return queryset.order_by("approval_order", "created_at")

    def _require_manage(self, approval):
        _require_scoped_permission(
            self.request.user,
            self._tenant(),
            "document.manage",
            approval.version.document.organization_unit,
        )

    def _require_pending_draft(self, approval):
        self._require_manage(approval)
        if approval.decision != DocumentApproval.Decision.PENDING:
            raise ValidationError("A decided approval assignment cannot be changed or removed.")
        if approval.version.status != DocumentVersion.Status.DRAFT:
            raise ValidationError("Approval assignments can change only while the version is draft.")
        if approval.version.document.current_version_id != approval.version_id:
            raise ValidationError("Approval assignments can change only on the current draft version.")

    def perform_create(self, serializer):
        tenant = self._tenant()
        candidate = serializer.validated_data["version"]
        with transaction.atomic():
            document, version = _lock_document_version(tenant, candidate.id)
            _require_scoped_permission(
                self.request.user, tenant, "document.manage", document.organization_unit
            )
            if (
                version.status != DocumentVersion.Status.DRAFT
                or document.current_version_id != version.id
            ):
                raise ValidationError("Approvers can be assigned only to the current draft version.")
            approval = serializer.save(version=version)
            record_audit_event(
                self.request.user,
                tenant,
                "document.approval_assign",
                "document_approval",
                approval.id,
                metadata={
                    "document_id": str(document.id),
                    "version_id": str(version.id),
                    "approver_id": approval.approver_id,
                    "approval_order": approval.approval_order,
                },
                request=self.request,
            )

    def perform_update(self, serializer):
        tenant = self._tenant()
        candidate = serializer.instance
        with transaction.atomic():
            _document, version = _lock_document_version(tenant, candidate.version_id)
            approval = (
                DocumentApproval.objects.select_for_update(of=("self",))
                .select_related("version__document__organization_unit", "approver")
                .filter(id=candidate.id, version=version, deleted_at__isnull=True)
                .first()
            )
            if not approval:
                raise ValidationError("Approval assignment not found.")
            serializer.instance = approval
            self._require_pending_draft(approval)
            serializer.save()
            record_audit_event(
                self.request.user,
                tenant,
                "document.approval_update",
                "document_approval",
                approval.id,
                request=self.request,
            )

    def perform_destroy(self, candidate):
        tenant = self._tenant()
        with transaction.atomic():
            _document, version = _lock_document_version(tenant, candidate.version_id)
            approval = (
                DocumentApproval.objects.select_for_update(of=("self",))
                .select_related("version__document__organization_unit", "approver")
                .filter(id=candidate.id, version=version, deleted_at__isnull=True)
                .first()
            )
            if not approval:
                raise ValidationError("Approval assignment not found.")
            self._require_pending_draft(approval)
            approval.deleted_at = timezone.now()
            approval.save(update_fields=["deleted_at", "updated_at"])
            record_audit_event(
                self.request.user,
                tenant,
                "document.approval_remove",
                "document_approval",
                approval.id,
                request=self.request,
            )

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        candidate = self.get_object()
        tenant = self._tenant()
        with transaction.atomic():
            document, version = _lock_document_version(tenant, candidate.version_id)
            approval = (
                DocumentApproval.objects.select_for_update(of=("self",))
                .select_related("approver")
                .filter(id=candidate.id, version=version, deleted_at__isnull=True)
                .first()
            )
            if not approval:
                raise ValidationError("Approval assignment not found.")

            _require_scoped_permission(
                request.user, tenant, "document.approve", document.organization_unit
            )
            if approval.approver_id != request.user.id:
                raise ValidationError("Only the assigned approver may decide this approval.")
            if approval.decision != DocumentApproval.Decision.PENDING:
                raise ValidationError("This approval has already been decided.")
            if (
                version.status != DocumentVersion.Status.REVIEW
                or document.current_version_id != version.id
            ):
                raise ValidationError(
                    "Approval decisions are accepted only for the current version in review."
                )

            earlier_blockers = version.approvals.filter(
                deleted_at__isnull=True,
                approval_order__lt=approval.approval_order,
            ).exclude(decision=DocumentApproval.Decision.APPROVED)
            if earlier_blockers.exists():
                raise ValidationError("Earlier approval stages must be approved first.")

            decision = request.data.get("decision")
            allowed = {
                DocumentApproval.Decision.APPROVED,
                DocumentApproval.Decision.REJECTED,
                DocumentApproval.Decision.CHANGES,
            }
            if decision not in allowed:
                raise ValidationError({"decision": "Invalid decision."})

            approval.decision = decision
            approval.comment = request.data.get("comment", "")
            approval.decided_at = timezone.now()
            approval.save(
                update_fields=["decision", "comment", "decided_at", "updated_at"]
            )

            if decision == DocumentApproval.Decision.APPROVED:
                remaining = version.approvals.filter(
                    deleted_at__isnull=True
                ).exclude(decision=DocumentApproval.Decision.APPROVED)
                if not remaining.exists():
                    now = timezone.now()
                    DocumentVersion.objects.filter(
                        document=document,
                        deleted_at__isnull=True,
                        status__in=[
                            DocumentVersion.Status.APPROVED,
                            DocumentVersion.Status.PUBLISHED,
                        ],
                    ).exclude(pk=version.pk).update(
                        status=DocumentVersion.Status.SUPERSEDED,
                        updated_at=now,
                    )
                    version.status = DocumentVersion.Status.APPROVED
                    version.save(update_fields=["status", "updated_at"])
                    document.status = Document.Status.APPROVED
                    document.save(update_fields=["status", "updated_at"])
            else:
                now = timezone.now()
                version.approvals.filter(
                    deleted_at__isnull=True,
                    decision=DocumentApproval.Decision.PENDING,
                ).exclude(pk=approval.pk).update(deleted_at=now, updated_at=now)
                version.status = DocumentVersion.Status.SUPERSEDED
                version.save(update_fields=["status", "updated_at"])
                document.status = Document.Status.DRAFT
                document.current_version = None
                document.save(
                    update_fields=["status", "current_version", "updated_at"]
                )

            record_audit_event(
                request.user,
                tenant,
                "document.approval_decide",
                "document_approval",
                approval.id,
                new_data={"decision": decision, "comment": approval.comment},
                metadata={
                    "document_id": str(document.id),
                    "version_id": str(version.id),
                },
                request=request,
            )
            if decision == DocumentApproval.Decision.APPROVED and version.status == DocumentVersion.Status.REVIEW:
                _notify_next_document_approvers(version)
            response_data = self.get_serializer(approval).data
        return Response(response_data)


class ReportTemplateViewSet(TM, viewsets.ModelViewSet):
    serializer_class = ReportTemplateSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "report.view")
        return ReportTemplate.objects.filter(deleted_at__isnull=True).filter(
            tenant__in=[tenant, None]
        )

    def perform_create(self, serializer):
        require_whole_tenant_permission(
            self.request.user, self._tenant(), "report.generate"
        )
        serializer.save(tenant=self._tenant())


class SoAViewSet(TM, viewsets.ViewSet):
    @action(detail=False, methods=["get"], url_path=r"(?P<assessment_id>[^/.]+)")
    def generate(self, request, assessment_id=None):
        tenant = self._tenant()
        assessment = (
            Assessment.objects.select_related("organization_unit", "framework_version")
            .filter(
                id=assessment_id,
                tenant=tenant,
                deleted_at__isnull=True,
            )
            .first()
        )
        if not assessment:
            raise ValidationError("Assessment not found.")
        _require_scoped_permission(
            request.user,
            tenant,
            "report.generate",
            assessment.organization_unit,
        )
        record_audit_event(
            request.user,
            tenant,
            "report.export",
            "assessment",
            assessment.id,
            metadata={
                "report": "soa",
                "format": "docx",
                "framework_version_id": str(assessment.framework_version_id),
            },
            request=request,
        )
        return soa_docx(assessment)

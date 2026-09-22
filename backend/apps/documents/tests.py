from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership

from .models import Document, DocumentApproval, DocumentVersion


User = get_user_model()


class DocumentsSmokeTests(TestCase):
    def test_models_import(self):
        self.assertTrue(Document and DocumentVersion)


class DocumentExportSecurityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="doc-admin", password="StrongPassword123!"
        )
        self.tenant = Tenant.objects.create(
            name="Document Security", code="doc-security"
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role_code="admin"
        )
        bootstrap_tenant_rbac(self.tenant, admin_user=self.user)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant, unit_type="company", code="HQ", name="HQ"
        )
        self.document = Document.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            document_type="policy",
            code="POL-1",
            title="Policy",
            owner=self.user,
        )
        self.version = DocumentVersion.objects.create(
            document=self.document,
            version="1.0",
            content="Controlled content",
            created_by=self.user,
        )
        self.document.current_version = self.version
        self.document.save(update_fields=["current_version", "updated_at"])
        self.auth(self.user)

    def auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def test_docx_export_creates_audit_event(self):
        response = self.client.get(
            f"/api/v1/document-versions/{self.version.id}/export/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="document.export",
                object_type="document_version",
                object_id=self.version.id,
            ).exists()
        )


class ControlledDocumentLifecycleTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="document-admin", password="StrongPassword123!"
        )
        self.viewer = User.objects.create_user(
            username="document-viewer", password="StrongPassword123!"
        )
        self.approver = User.objects.create_user(
            username="document-approver", password="StrongPassword123!"
        )
        self.approver2 = User.objects.create_user(
            username="document-approver-2", password="StrongPassword123!"
        )
        self.outsider = User.objects.create_user(
            username="document-outsider", password="StrongPassword123!"
        )

        self.tenant = Tenant.objects.create(name="Docs Tenant", code="docs-tenant")
        for user, role_code in [
            (self.admin, "admin"),
            (self.viewer, "member"),
            (self.approver, "member"),
            (self.approver2, "member"),
        ]:
            TenantMembership.objects.create(
                tenant=self.tenant, user=user, role_code=role_code
            )

        self.other_tenant = Tenant.objects.create(
            name="Other Docs", code="other-docs"
        )
        TenantMembership.objects.create(
            tenant=self.other_tenant, user=self.outsider, role_code="member"
        )

        self.roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type="department",
            code="GRC",
            name="GRC",
        )
        UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.viewer,
            role=self.roles["viewer"],
            organization_unit=self.unit,
        )
        UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.approver,
            role=self.roles["grc_manager"],
            organization_unit=self.unit,
        )
        UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.approver2,
            role=self.roles["grc_manager"],
            organization_unit=self.unit,
        )

        self.document = Document.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            document_type=Document.Type.POLICY,
            code="POL-GRC",
            title="GRC Policy",
            owner=self.admin,
        )
        self.version = DocumentVersion.objects.create(
            document=self.document,
            version="1.0",
            content="Draft policy",
            change_summary="Initial draft",
            created_by=self.admin,
        )
        self.document.current_version = self.version
        self.document.save(update_fields=["current_version", "updated_at"])
        self.auth(self.admin)

    def auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def assign(self, user=None, order=1):
        return DocumentApproval.objects.create(
            version=self.version,
            approver=user or self.approver,
            approval_order=order,
        )

    def submit(self):
        return self.client.post(
            f"/api/v1/document-versions/{self.version.id}/submit/",
            {},
            format="json",
        )

    def test_read_only_status_fields_cannot_forge_lifecycle(self):
        document_response = self.client.patch(
            f"/api/v1/documents/{self.document.id}/",
            {"status": Document.Status.APPROVED},
            format="json",
        )
        version_response = self.client.patch(
            f"/api/v1/document-versions/{self.version.id}/",
            {"status": DocumentVersion.Status.APPROVED},
            format="json",
        )

        self.assertEqual(document_response.status_code, 200)
        self.assertEqual(version_response.status_code, 200)
        self.document.refresh_from_db()
        self.version.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.DRAFT)
        self.assertEqual(self.version.status, DocumentVersion.Status.DRAFT)

    def test_viewer_cannot_mutate_version_or_approval(self):
        approval = self.assign()
        self.auth(self.viewer)

        version_response = self.client.patch(
            f"/api/v1/document-versions/{self.version.id}/",
            {"content": "unauthorized"},
            format="json",
        )
        approval_response = self.client.patch(
            f"/api/v1/document-approvals/{approval.id}/",
            {"approval_order": 9},
            format="json",
        )

        self.assertEqual(version_response.status_code, 403)
        self.assertEqual(approval_response.status_code, 403)
        self.version.refresh_from_db()
        approval.refresh_from_db()
        self.assertEqual(self.version.content, "Draft policy")
        self.assertEqual(approval.approval_order, 1)

    def test_cross_tenant_approver_is_rejected(self):
        response = self.client.post(
            "/api/v1/document-approvals/",
            {
                "version": str(self.version.id),
                "approver": self.outsider.id,
                "approval_order": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_workspace_participants_are_permission_aware(self):
        owner_response = self.client.get(
            f"/api/v1/documents/participants/?organization_unit={self.unit.id}&kind=owner"
        )
        approver_response = self.client.get(
            f"/api/v1/documents/participants/?organization_unit={self.unit.id}&kind=approver"
        )

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(approver_response.status_code, 200)
        owner_ids = {row["id"] for row in owner_response.data["results"]}
        approver_ids = {row["id"] for row in approver_response.data["results"]}
        self.assertIn(self.viewer.id, owner_ids)
        self.assertIn(self.approver.id, approver_ids)
        self.assertNotIn(self.viewer.id, approver_ids)
        self.assertNotIn(self.outsider.id, owner_ids)

    def test_submit_requires_approver_and_locks_reviewed_version(self):
        missing = self.submit()
        self.assertEqual(missing.status_code, 400)

        self.assign()
        submitted = self.submit()
        self.assertEqual(submitted.status_code, 200)

        edit = self.client.patch(
            f"/api/v1/document-versions/{self.version.id}/",
            {"content": "silent rewrite"},
            format="json",
        )
        self.assertEqual(edit.status_code, 400)
        self.version.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(self.version.status, DocumentVersion.Status.REVIEW)
        self.assertEqual(self.document.status, Document.Status.REVIEW)
        self.assertEqual(self.version.content, "Draft policy")

    def test_decision_requires_review_and_cannot_be_replayed(self):
        approval = self.assign()
        self.auth(self.approver)
        before_review = self.client.post(
            f"/api/v1/document-approvals/{approval.id}/decide/",
            {"decision": DocumentApproval.Decision.APPROVED},
            format="json",
        )
        self.assertEqual(before_review.status_code, 400)

        self.auth(self.admin)
        self.assertEqual(self.submit().status_code, 200)

        self.auth(self.approver)
        with CaptureQueriesContext(connection) as captured:
            first = self.client.post(
                f"/api/v1/document-approvals/{approval.id}/decide/",
                {
                    "decision": DocumentApproval.Decision.APPROVED,
                    "comment": "Approved",
                },
                format="json",
            )
        lock_queries = [
            row["sql"].lower()
            for row in captured.captured_queries
            if "for update" in row["sql"].lower()
        ]
        self.assertTrue(
            any("documents_document" in sql for sql in lock_queries),
            "Document aggregate root must be row-locked before an approval decision.",
        )
        self.assertTrue(
            any("documents_documentversion" in sql for sql in lock_queries),
            "Document version must be row-locked before an approval decision.",
        )
        self.assertTrue(
            any("documents_documentapproval" in sql for sql in lock_queries),
            "Approval row must be row-locked before applying the decision.",
        )
        second = self.client.post(
            f"/api/v1/document-approvals/{approval.id}/decide/",
            {"decision": DocumentApproval.Decision.APPROVED},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

        self.version.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(self.version.status, DocumentVersion.Status.APPROVED)
        self.assertEqual(self.document.status, Document.Status.APPROVED)

        self.auth(self.admin)
        delete_decided = self.client.delete(
            f"/api/v1/document-approvals/{approval.id}/"
        )
        self.assertEqual(delete_decided.status_code, 400)

    def test_ordered_approval_stages_are_enforced(self):
        first = self.assign(self.approver, order=1)
        second = self.assign(self.approver2, order=2)
        self.assertEqual(self.submit().status_code, 200)

        self.auth(self.approver2)
        too_early = self.client.post(
            f"/api/v1/document-approvals/{second.id}/decide/",
            {"decision": DocumentApproval.Decision.APPROVED},
            format="json",
        )
        self.assertEqual(too_early.status_code, 400)

        self.auth(self.approver)
        ok = self.client.post(
            f"/api/v1/document-approvals/{first.id}/decide/",
            {"decision": DocumentApproval.Decision.APPROVED},
            format="json",
        )
        self.assertEqual(ok.status_code, 200)

        self.auth(self.approver2)
        final = self.client.post(
            f"/api/v1/document-approvals/{second.id}/decide/",
            {"decision": DocumentApproval.Decision.APPROVED},
            format="json",
        )
        self.assertEqual(final.status_code, 200)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, DocumentVersion.Status.APPROVED)

    def test_changes_requested_ends_review_without_rewriting_history(self):
        first = self.assign(self.approver, order=1)
        second = self.assign(self.approver2, order=2)
        self.assertEqual(self.submit().status_code, 200)

        self.auth(self.approver)
        response = self.client.post(
            f"/api/v1/document-approvals/{first.id}/decide/",
            {
                "decision": DocumentApproval.Decision.CHANGES,
                "comment": "Revise section 4.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        first.refresh_from_db()
        second.refresh_from_db()
        self.version.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(first.decision, DocumentApproval.Decision.CHANGES)
        self.assertEqual(first.comment, "Revise section 4.")
        self.assertIsNotNone(second.deleted_at)
        self.assertEqual(self.version.status, DocumentVersion.Status.SUPERSEDED)
        self.assertEqual(self.document.status, Document.Status.DRAFT)
        self.assertIsNone(self.document.current_version_id)

    def test_removed_pending_approver_can_be_reassigned_without_duplicate(self):
        approval = self.assign()
        removed = self.client.delete(
            f"/api/v1/document-approvals/{approval.id}/"
        )
        self.assertEqual(removed.status_code, 204)

        reassigned = self.client.post(
            "/api/v1/document-approvals/",
            {
                "version": str(self.version.id),
                "approver": self.approver.id,
                "approval_order": 3,
            },
            format="json",
        )
        self.assertEqual(reassigned.status_code, 201)
        approval.refresh_from_db()
        self.assertIsNone(approval.deleted_at)
        self.assertEqual(approval.approval_order, 3)
        self.assertEqual(
            DocumentApproval.objects.filter(
                version=self.version, approver=self.approver
            ).count(),
            1,
        )

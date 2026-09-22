from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.assessments.models import Assessment, AssessmentItem
from apps.documents.models import Document, DocumentApproval, DocumentVersion
from apps.findings.models import Finding
from apps.frameworks.models import Framework, FrameworkVersion, Requirement
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.internal_audits.models import AuditEngagement, Workpaper
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership


class WorkCenterTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="work-admin", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Work Tenant", code="work-tenant")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="admin")
        bootstrap_tenant_rbac(self.tenant, admin_user=self.user)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            code="HQ",
            name="Head Office",
        )
        self.other_unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type=OrganizationUnit.UnitType.BUSINESS_UNIT,
            code="OPS",
            name="Operations",
        )
        self.framework = Framework.objects.create(
            tenant=self.tenant,
            code="work-framework",
            name="Work Framework",
            status=Framework.Status.ACTIVE,
        )
        self.version = FrameworkVersion.objects.create(
            framework=self.framework,
            version_code="1.0",
            status=FrameworkVersion.Status.ACTIVE,
        )
        self.requirement = Requirement.objects.create(
            framework_version=self.version,
            code="REQ-1",
            title="Assigned requirement",
        )
        self.assessment = Assessment.objects.create(
            tenant=self.tenant,
            framework_version=self.version,
            organization_unit=self.unit,
            title="Quarterly Compliance Review",
            owner=self.user,
            status=Assessment.Status.IN_REVIEW,
            due_date=timezone.localdate() + timedelta(days=3),
        )
        self.assessment_item = AssessmentItem.objects.create(
            assessment=self.assessment,
            requirement=self.requirement,
            requirement_code_snapshot=self.requirement.code,
            requirement_title_snapshot=self.requirement.title,
            assigned_to=self.user,
            status=AssessmentItem.Status.NOT_ASSESSED,
        )
        self.overdue_action = Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Rotate privileged credentials",
            owner=self.user,
            priority=Action.Priority.HIGH,
            status=Action.Status.TODO,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        self.review_action = Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Review remediation evidence",
            owner=self.user,
            reviewer=self.user,
            status=Action.Status.REVIEW,
            due_date=timezone.localdate() + timedelta(days=10),
        )
        self.finding = Finding.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Excess privileged accounts",
            owner=self.user,
            severity=Finding.Severity.HIGH,
            status=Finding.Status.IN_REMEDIATION,
            due_date=timezone.localdate() + timedelta(days=2),
        )
        self.document = Document.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            document_type=Document.Type.POLICY,
            code="POL-001",
            title="Access Control Policy",
            owner=self.user,
            status=Document.Status.REVIEW,
        )
        self.document_version = DocumentVersion.objects.create(
            document=self.document,
            version="1.0",
            created_by=self.user,
            status=DocumentVersion.Status.REVIEW,
        )
        self.approval = DocumentApproval.objects.create(
            version=self.document_version,
            approver=self.user,
            decision=DocumentApproval.Decision.PENDING,
        )
        self.engagement = AuditEngagement.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Identity Access Audit",
            audit_type=AuditEngagement.AuditType.INTERNAL,
            lead_auditor=self.user,
            status=AuditEngagement.Status.IN_PROGRESS,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=5),
        )
        self.draft_workpaper = Workpaper.objects.create(
            engagement=self.engagement,
            title="Privileged access sample",
            procedure="Inspect a sample of privileged accounts.",
            tester=self.user,
            status=Workpaper.Status.DRAFT,
        )
        self.ready_workpaper = Workpaper.objects.create(
            engagement=self.engagement,
            title="MFA operating effectiveness",
            procedure="Review MFA enforcement evidence.",
            tester=self.user,
            status=Workpaper.Status.READY,
        )
        self._authenticate(self.user)

    def _authenticate(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _get(self):
        return self.client.get("/api/v1/work-center/")

    def test_work_center_aggregates_authoritative_assignments_and_attention(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        sources = {item["source"] for item in body["items"]}
        self.assertTrue(
            {
                "action",
                "finding",
                "assessment_item",
                "assessment_review",
                "document_approval",
                "audit_engagement",
                "audit_workpaper",
                "audit_workpaper_review",
            }.issubset(sources)
        )
        by_title = {item["title"]: item for item in body["items"]}
        self.assertTrue(by_title[self.overdue_action.title]["is_overdue"])
        self.assertEqual(by_title[self.overdue_action.title]["attention"], "overdue")
        self.assertTrue(by_title[self.finding.title]["is_due_soon"])
        self.assertTrue(by_title[self.review_action.title]["is_review"])
        self.assertEqual(by_title[self.review_action.title]["attention"], "review")
        self.assertTrue(all(item["can_act"] for item in body["items"]))
        self.assertEqual(body["summary"]["total"], len(body["items"]))
        self.assertGreaterEqual(body["summary"]["overdue"], 1)
        self.assertGreaterEqual(body["summary"]["due_soon"], 1)
        self.assertGreaterEqual(body["summary"]["review"], 4)
        self.assertEqual(body["due_soon_days"], 7)

    def test_work_center_does_not_leak_another_tenant(self):
        other_tenant = Tenant.objects.create(name="Foreign Tenant", code="foreign-work")
        other_unit = OrganizationUnit.objects.create(
            tenant=other_tenant,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            code="FOREIGN",
            name="Foreign Company",
        )
        Action.objects.create(
            tenant=other_tenant,
            organization_unit=other_unit,
            title="Foreign tenant action",
            owner=self.user,
            due_date=timezone.localdate() - timedelta(days=4),
        )
        Finding.objects.create(
            tenant=other_tenant,
            organization_unit=other_unit,
            title="Foreign tenant finding",
            owner=self.user,
        )

        response = self._get()
        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.json()["items"]}
        self.assertNotIn("Foreign tenant action", titles)
        self.assertNotIn("Foreign tenant finding", titles)

    def test_work_center_respects_source_scope_and_reports_actionability(self):
        User = get_user_model()
        scoped_user = User.objects.create_user(username="work-scoped", password="StrongPassword123!")
        TenantMembership.objects.create(tenant=self.tenant, user=scoped_user, role_code="viewer")
        roles = bootstrap_tenant_rbac(self.tenant)
        UserRoleScope.objects.create(
            user=scoped_user,
            tenant=self.tenant,
            role=roles["viewer"],
            organization_unit=self.unit,
        )
        Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Visible scoped action",
            owner=scoped_user,
        )
        Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.other_unit,
            title="Hidden sibling action",
            owner=scoped_user,
        )
        Action.objects.create(
            tenant=self.tenant,
            organization_unit=None,
            title="Hidden whole-tenant action",
            owner=scoped_user,
        )
        Finding.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Visible scoped finding",
            owner=scoped_user,
        )
        Finding.objects.create(
            tenant=self.tenant,
            organization_unit=self.other_unit,
            title="Hidden sibling finding",
            owner=scoped_user,
        )
        self._authenticate(scoped_user)

        response = self._get()
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        by_title = {item["title"]: item for item in items}
        self.assertIn("Visible scoped action", by_title)
        self.assertIn("Visible scoped finding", by_title)
        self.assertNotIn("Hidden sibling action", by_title)
        self.assertNotIn("Hidden whole-tenant action", by_title)
        self.assertNotIn("Hidden sibling finding", by_title)
        self.assertFalse(by_title["Visible scoped action"]["can_act"])
        self.assertFalse(by_title["Visible scoped finding"]["can_act"])

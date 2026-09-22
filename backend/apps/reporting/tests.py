from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.audit.models import AuditEvent
from apps.assessments.models import Assessment
from apps.controls.models import Control, ControlImplementation
from apps.documents.models import ReportTemplate
from apps.frameworks.models import Framework, FrameworkVersion
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.risks.models import Risk, RiskEvaluation, RiskMethodology
from apps.tenancy.models import Tenant, TenantMembership

from .template_engine import render_html, safe_report_url_fetcher


class ReportingSmokeTests(TestCase):
    def test_import(self):
        from .views import ManagementDashboardView

        self.assertTrue(ManagementDashboardView)

    def test_html_context_is_autoescaped(self):
        rendered = render_html("<p>{{ value }}</p>", {"value": "<script>alert(1)</script>"})
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_report_fetcher_blocks_network_and_local_files(self):
        for url in (
            "http://127.0.0.1/internal",
            "https://example.invalid/asset",
            "file:///etc/passwd",
        ):
            with self.assertRaises(ValueError):
                safe_report_url_fetcher(url)


class ManagementDashboardTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="dashboard-admin", password="StrongPassword123!"
        )
        self.tenant = Tenant.objects.create(name="Dashboard Tenant", code="dashboard-tenant")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role_code="admin"
        )
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
            code="pilot-security",
            name="Pilot Security Baseline",
            status=Framework.Status.ACTIVE,
        )
        self.version = FrameworkVersion.objects.create(
            framework=self.framework,
            version_code="2026.1",
            status=FrameworkVersion.Status.ACTIVE,
        )
        self.assessment = Assessment.objects.create(
            tenant=self.tenant,
            framework_version=self.version,
            organization_unit=self.unit,
            title="Head Office Assessment",
            owner=self.user,
            status=Assessment.Status.IN_PROGRESS,
            overall_score=Decimal("78.000"),
            progress_percent=Decimal("67.000"),
            due_date=timezone.localdate() + timedelta(days=5),
        )
        self.methodology = RiskMethodology.objects.create(
            tenant=self.tenant,
            name="5x5",
            likelihood_scale=[],
            impact_scale=[],
            matrix={},
            thresholds=[],
            is_default=True,
        )
        self.risk = Risk.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            code="R-001",
            title="Privileged access compromise",
            owner=self.user,
            status=Risk.Status.OPEN,
            review_date=timezone.localdate() + timedelta(days=8),
        )
        RiskEvaluation.objects.create(
            risk=self.risk,
            methodology=self.methodology,
            evaluation_type=RiskEvaluation.EvaluationType.RESIDUAL,
            likelihood=Decimal("5.00"),
            impact=Decimal("5.00"),
            score=Decimal("25.0000"),
            level="critical",
            evaluated_by=self.user,
        )
        self.overdue_action = Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Deploy MFA",
            owner=self.user,
            priority=Action.Priority.HIGH,
            status=Action.Status.TODO,
            source_type="risk",
            source_id=self.risk.id,
            due_date=timezone.localdate() - timedelta(days=2),
        )
        Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Review suppliers",
            owner=self.user,
            priority=Action.Priority.MEDIUM,
            status=Action.Status.IN_PROGRESS,
            due_date=timezone.localdate() + timedelta(days=7),
        )
        control = Control.objects.create(
            tenant=self.tenant,
            code="IAM-1",
            title="Strong authentication",
            status=Control.Status.ACTIVE,
        )
        ControlImplementation.objects.create(
            tenant=self.tenant,
            control=control,
            organization_unit=self.unit,
            owner=self.user,
            implementation_status=ControlImplementation.ImplementationStatus.IMPLEMENTED,
            effectiveness=ControlImplementation.Effectiveness.EFFECTIVE,
        )
        self._authenticate(self.user)

    def _authenticate(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _get_dashboard(self):
        return self.client.get("/api/v1/dashboard/management/")

    def test_dashboard_returns_real_executive_aggregates(self):
        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["dashboard_schema_version"], 2)
        self.assertEqual(body["compliance_score"], 78.0)
        self.assertEqual(body["high_critical_residual_risks"], 1)
        self.assertEqual(body["overdue_actions"], 1)
        self.assertEqual(body["effective_controls_percent"], 100.0)
        self.assertEqual(body["assessments_due"], 1)

        self.assertEqual(len(body["framework_summaries"]), 1)
        framework = body["framework_summaries"][0]
        self.assertEqual(framework["framework_code"], "pilot-security")
        self.assertEqual(framework["average_score"], 78.0)
        self.assertEqual(framework["average_progress"], 67.0)

        self.assertEqual(body["risk_heatmap"][0]["count"], 1)
        self.assertEqual(body["risk_heatmap"][0]["max_level"], "critical")
        self.assertEqual(body["top_risks"][0]["code"], "R-001")
        self.assertIn("Deploy MFA", [item["title"] for item in body["attention_actions"]])
        deadline_types = {item["type"] for item in body["upcoming_deadlines"]}
        self.assertTrue({"assessment", "action", "risk_review"}.issubset(deadline_types))

    def test_dashboard_does_not_leak_another_tenant(self):
        other_tenant = Tenant.objects.create(name="Other Tenant", code="other-dashboard")
        other_unit = OrganizationUnit.objects.create(
            tenant=other_tenant,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            code="OTHER",
            name="Other Company",
        )
        other_framework = Framework.objects.create(
            tenant=other_tenant,
            code="other-framework",
            name="Other Framework",
        )
        other_version = FrameworkVersion.objects.create(
            framework=other_framework, version_code="1"
        )
        Assessment.objects.create(
            tenant=other_tenant,
            framework_version=other_version,
            organization_unit=other_unit,
            title="Other Assessment",
            owner=self.user,
            overall_score=Decimal("10.000"),
            progress_percent=Decimal("10.000"),
            due_date=timezone.localdate() + timedelta(days=1),
        )
        other_methodology = RiskMethodology.objects.create(
            tenant=other_tenant,
            name="Other 5x5",
        )
        other_risk = Risk.objects.create(
            tenant=other_tenant,
            organization_unit=other_unit,
            code="R-X",
            title="Foreign tenant risk",
            owner=self.user,
            status=Risk.Status.OPEN,
        )
        RiskEvaluation.objects.create(
            risk=other_risk,
            methodology=other_methodology,
            evaluation_type=RiskEvaluation.EvaluationType.RESIDUAL,
            likelihood=Decimal("5.00"),
            impact=Decimal("5.00"),
            score=Decimal("25.0000"),
            level="critical",
            evaluated_by=self.user,
        )
        Action.objects.create(
            tenant=other_tenant,
            organization_unit=other_unit,
            title="Foreign tenant action",
            owner=self.user,
            due_date=timezone.localdate() - timedelta(days=5),
        )

        response = self._get_dashboard()
        body = response.json()
        self.assertEqual(body["compliance_score"], 78.0)
        self.assertEqual(body["high_critical_residual_risks"], 1)
        self.assertEqual(body["overdue_actions"], 1)
        self.assertNotIn("other-framework", [row["framework_code"] for row in body["framework_summaries"]])
        self.assertNotIn("R-X", [row["code"] for row in body["top_risks"]])
        self.assertNotIn("Foreign tenant action", [row["title"] for row in body["attention_actions"]])

    def test_dashboard_respects_report_view_organization_scope(self):
        Assessment.objects.create(
            tenant=self.tenant,
            framework_version=self.version,
            organization_unit=self.other_unit,
            title="Operations Assessment",
            owner=self.user,
            status=Assessment.Status.IN_PROGRESS,
            overall_score=Decimal("20.000"),
            progress_percent=Decimal("20.000"),
            due_date=timezone.localdate() + timedelta(days=3),
        )
        other_risk = Risk.objects.create(
            tenant=self.tenant,
            organization_unit=self.other_unit,
            code="R-OPS",
            title="Operations-only risk",
            owner=self.user,
            status=Risk.Status.OPEN,
        )
        RiskEvaluation.objects.create(
            risk=other_risk,
            methodology=self.methodology,
            evaluation_type=RiskEvaluation.EvaluationType.RESIDUAL,
            likelihood=Decimal("4.00"),
            impact=Decimal("5.00"),
            score=Decimal("20.0000"),
            level="critical",
            evaluated_by=self.user,
        )
        Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.other_unit,
            title="Operations-only action",
            owner=self.user,
            due_date=timezone.localdate() - timedelta(days=1),
        )

        User = get_user_model()
        scoped_user = User.objects.create_user(
            username="dashboard-scoped", password="StrongPassword123!"
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=scoped_user, role_code="viewer"
        )
        roles = bootstrap_tenant_rbac(self.tenant)
        UserRoleScope.objects.create(
            user=scoped_user,
            tenant=self.tenant,
            role=roles["viewer"],
            organization_unit=self.unit,
        )
        self._authenticate(scoped_user)

        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["compliance_score"], 78.0)
        self.assertEqual(body["high_critical_residual_risks"], 1)
        self.assertEqual(body["overdue_actions"], 1)
        self.assertNotIn("R-OPS", [row["code"] for row in body["top_risks"]])
        self.assertNotIn("Operations-only action", [row["title"] for row in body["attention_actions"]])


class ReportExportAuditTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="report-admin", password="StrongPassword123!"
        )
        self.tenant = Tenant.objects.create(name="Report Tenant", code="report-tenant")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role_code="admin"
        )
        self.template = ReportTemplate.objects.create(
            tenant=self.tenant,
            template_type="custom",
            name="Safe Template",
            configuration={"html_template": "<h1>{{ title }}</h1>"},
        )
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def test_html_report_export_is_audited(self):
        response = self.client.post(
            "/api/v1/reports/render-template/",
            {
                "template_id": str(self.template.id),
                "format": "html",
                "context": {"title": "Executive"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="report.export",
                object_type="report_template",
                object_id=self.template.id,
                outcome="success",
            ).exists()
        )

    def test_unsupported_report_format_is_rejected(self):
        response = self.client.post(
            "/api/v1/reports/render-template/",
            {"template_id": str(self.template.id), "format": "xml", "context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

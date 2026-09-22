from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.assessments.models import Assessment, AssessmentItem
from apps.controls.models import Control, ControlCategory
from apps.frameworks.models import Framework, FrameworkVersion, Requirement
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.risks.models import Risk, RiskCategory
from apps.tenancy.models import Tenant, TenantMembership


User = get_user_model()


class QueryAmplificationRegressionTests(APITestCase):
    """List serialization must not add one-or-more SQL queries per returned row."""

    EXTRA_QUERY_BUDGET = 3

    def setUp(self):
        self.user = User.objects.create_user(username="perf-admin", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Performance Tenant", code="perf-tenant")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="admin")
        bootstrap_tenant_rbac(self.tenant, admin_user=self.user)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type="company",
            code="PERF-HQ",
            name="Performance HQ",
        )
        self.risk_category = RiskCategory.objects.create(tenant=self.tenant, code="perf-risk", name="Performance Risk")
        self.control_category = ControlCategory.objects.create(tenant=self.tenant, code="perf-control", name="Performance Control")
        self.framework = Framework.objects.create(
            tenant=self.tenant,
            code="perf-framework",
            name="Performance Framework",
            content_source=Framework.ContentSource.INTERNAL,
            license_type=Framework.LicenseType.INTERNAL,
        )
        self.version = FrameworkVersion.objects.create(
            framework=self.framework,
            version_code="perf-1",
            title="Performance fixture",
        )
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _query_count(self, path):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        return len(captured.captured_queries)

    def _assert_constant_scale(self, path, add_rows):
        small = self._query_count(path)
        add_rows()
        large = self._query_count(path)
        self.assertLessEqual(
            large,
            small + self.EXTRA_QUERY_BUDGET,
            f"SQL query count scaled with result size for {path}: small={small}, large={large}",
        )

    def _create_risks(self, start, count):
        for index in range(start, start + count):
            Risk.objects.create(
                tenant=self.tenant,
                organization_unit=self.unit,
                category=self.risk_category,
                code=f"PERF-R-{index:03d}",
                title=f"Performance risk {index}",
                owner=self.user,
                status=Risk.Status.OPEN,
            )

    def _create_controls(self, start, count):
        for index in range(start, start + count):
            Control.objects.create(
                tenant=self.tenant,
                category=self.control_category,
                code=f"PERF-C-{index:03d}",
                title=f"Performance control {index}",
                status=Control.Status.ACTIVE,
                created_by=self.user,
            )

    def _create_assessments(self, start, count):
        for index in range(start, start + count):
            Assessment.objects.create(
                tenant=self.tenant,
                framework_version=self.version,
                organization_unit=self.unit,
                title=f"Performance assessment {index}",
                owner=self.user,
            )

    def _create_assessment_items(self, assessment, start, count):
        for index in range(start, start + count):
            requirement = Requirement.objects.create(
                framework_version=self.version,
                code=f"PERF-REQ-{index:03d}",
                title=f"Performance requirement {index}",
                sort_order=index,
            )
            AssessmentItem.objects.create(
                assessment=assessment,
                requirement=requirement,
                requirement_code_snapshot=requirement.code,
                requirement_title_snapshot=requirement.title,
            )

    def test_risk_list_query_count_does_not_scale_per_row(self):
        self._create_risks(0, 1)
        self._assert_constant_scale("/api/v1/risks/?page_size=50", lambda: self._create_risks(1, 19))

    def test_control_list_query_count_does_not_scale_per_row(self):
        self._create_controls(0, 1)
        self._assert_constant_scale("/api/v1/controls/?page_size=50", lambda: self._create_controls(1, 19))

    def test_assessment_list_query_count_does_not_scale_per_row(self):
        self._create_assessments(0, 1)
        self._assert_constant_scale("/api/v1/assessments/?page_size=50", lambda: self._create_assessments(1, 19))

    def test_assessment_item_list_query_count_does_not_scale_per_row(self):
        assessment = Assessment.objects.create(
            tenant=self.tenant,
            framework_version=self.version,
            organization_unit=self.unit,
            title="Assessment item query budget",
            owner=self.user,
        )
        self._create_assessment_items(assessment, 0, 1)
        path = f"/api/v1/assessment-items/?assessment={assessment.id}&page_size=50"
        self._assert_constant_scale(path, lambda: self._create_assessment_items(assessment, 1, 19))

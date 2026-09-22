import uuid
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Tenant, TenantMembership
from apps.organizations.models import OrganizationUnit
from apps.audit.models import AuditEvent

User = get_user_model()

class TenantIsolationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="StrongPassword123!")
        self.tenant_a = Tenant.objects.create(name="Tenant A", code="tenant-a")
        self.tenant_b = Tenant.objects.create(name="Tenant B", code="tenant-b")
        TenantMembership.objects.create(tenant=self.tenant_a, user=self.user, role_code="admin")
        OrganizationUnit.objects.create(tenant=self.tenant_a, unit_type="company", code="A-COMP", name="A Company")
        OrganizationUnit.objects.create(tenant=self.tenant_b, unit_type="company", code="B-COMP", name="B Company")
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_list_is_scoped_to_selected_tenant(self):
        response = self.client.get("/api/v1/organization-units/", HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(response.status_code, 200)
        payload = response.json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["code"], "A-COMP")

    def test_non_member_cannot_select_other_tenant(self):
        response = self.client.get("/api/v1/organization-units/", HTTP_X_TENANT_ID=str(self.tenant_b.id))
        self.assertEqual(response.status_code, 403)

    def test_invalid_tenant_header_is_rejected(self):
        response = self.client.get("/api/v1/organization-units/", HTTP_X_TENANT_ID="not-a-uuid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_TENANT_ID")

    def test_create_records_audit_event(self):
        response = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "department", "code": "IT", "name": "IT"},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(AuditEvent.objects.filter(tenant=self.tenant_a, action="organization.create").exists())

    def test_missing_tenant_header_is_validation_error(self):
        response = self.client.get("/api/v1/organization-units/")
        self.assertEqual(response.status_code, 400)

class HealthTests(APITestCase):
    def test_live_endpoint_is_public(self):
        response = self.client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

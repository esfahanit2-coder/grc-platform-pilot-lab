import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership
from .models import UserRoleScope
from .services import bootstrap_tenant_rbac, create_pending_mfa_device, has_tenant_permission

User = get_user_model()


class RBACScopeTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", password="StrongPassword123!")
        self.viewer = User.objects.create_user(username="scoped", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Tenant A", code="tenant-a")
        TenantMembership.objects.create(tenant=self.tenant, user=self.admin, role_code="admin")
        TenantMembership.objects.create(tenant=self.tenant, user=self.viewer, role_code="member")
        self.roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.company_a = OrganizationUnit.objects.create(tenant=self.tenant, unit_type="company", code="A", name="A")
        self.company_b = OrganizationUnit.objects.create(tenant=self.tenant, unit_type="company", code="B", name="B")
        self.department_a = OrganizationUnit.objects.create(tenant=self.tenant, parent=self.company_a, unit_type="department", code="A-IT", name="IT")
        UserRoleScope.objects.create(tenant=self.tenant, user=self.viewer, role=self.roles["grc_manager"], organization_unit=self.company_a)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}", HTTP_X_TENANT_ID=str(self.tenant.id))

    def test_tenant_admin_has_manage_permission(self):
        self.assertTrue(has_tenant_permission(self.admin, self.tenant, "organization.manage"))

    def test_scoped_role_applies_to_descendant_not_sibling(self):
        self.assertTrue(has_tenant_permission(self.viewer, self.tenant, "organization.manage", self.department_a))
        self.assertFalse(has_tenant_permission(self.viewer, self.tenant, "organization.manage", self.company_b))

    def test_scoped_org_api_hides_sibling(self):
        self.auth(self.viewer)
        response = self.client.get("/api/v1/organization-units/")
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(str(self.company_a.id), ids)
        self.assertIn(str(self.department_a.id), ids)
        self.assertNotIn(str(self.company_b.id), ids)

    def test_scoped_manager_cannot_create_new_root(self):
        self.auth(self.viewer)
        response = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "company", "code": "ESCAPE", "name": "Escaped root"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_scoped_manager_cannot_move_unit_to_inaccessible_sibling(self):
        self.auth(self.viewer)
        response = self.client.patch(
            f"/api/v1/organization-units/{self.department_a.id}/",
            {"parent": str(self.company_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_tree_starts_at_scoped_root(self):
        self.auth(self.viewer)
        response = self.client.get("/api/v1/organization-units/tree/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "A")
        self.assertEqual(response.data[0]["children"][0]["code"], "A-IT")


class MFAFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="mfa-user", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Secure", code="secure")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="member")

    def test_existing_mfa_requires_challenge_and_otp(self):
        device, secret, _ = create_pending_mfa_device(self.user)
        device.is_active = True
        device.save(update_fields=["is_active", "updated_at"])
        response = self.client.post("/api/v1/auth/token", {"username": "mfa-user", "password": "StrongPassword123!"}, format="json")
        self.assertEqual(response.status_code, 202)
        otp = pyotp.TOTP(secret).now()
        verify = self.client.post("/api/v1/auth/mfa/verify-login", {"challenge": response.data["challenge"], "otp": otp}, format="json")
        self.assertEqual(verify.status_code, 200)
        self.assertIn("access", verify.data)

    def test_accepted_totp_cannot_be_replayed(self):
        device, secret, _ = create_pending_mfa_device(self.user)
        device.is_active = True
        device.save(update_fields=["is_active", "updated_at"])
        login = self.client.post("/api/v1/auth/token", {"username": "mfa-user", "password": "StrongPassword123!"}, format="json")
        otp = pyotp.TOTP(secret).now()
        first = self.client.post("/api/v1/auth/mfa/verify-login", {"challenge": login.data["challenge"], "otp": otp}, format="json")
        second = self.client.post("/api/v1/auth/mfa/verify-login", {"challenge": login.data["challenge"], "otp": otp}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)
        device.refresh_from_db()
        self.assertIsNotNone(device.last_used_step)

    def test_tenant_required_mfa_enrollment(self):
        self.tenant.settings = {"security": {"require_mfa": True, "password_min_length": 12, "session_minutes": 60}}
        self.tenant.save(update_fields=["settings", "updated_at"])
        login = self.client.post("/api/v1/auth/token", {"username": "mfa-user", "password": "StrongPassword123!"}, format="json")
        self.assertEqual(login.status_code, 428)
        enroll = self.client.post("/api/v1/auth/mfa/enroll", {"challenge": login.data["challenge"]}, format="json")
        self.assertEqual(enroll.status_code, 200)
        finish = self.client.post(
            "/api/v1/auth/mfa/enroll/verify",
            {"challenge": enroll.data["challenge"], "device_id": enroll.data["device_id"], "otp": pyotp.TOTP(enroll.data["secret"]).now()},
            format="json",
        )
        self.assertEqual(finish.status_code, 200)
        self.assertTrue(finish.data["mfa_enabled"])
        self.assertIn("access", finish.data)

    def test_login_is_rate_limited_by_public_auth_throttle(self):
        cache.clear()
        payload = {"username": "mfa-user", "password": "wrong-password"}
        responses = [
            self.client.post("/api/v1/auth/token", payload, format="json", REMOTE_ADDR="203.0.113.10")
            for _ in range(11)
        ]
        self.assertTrue(all(response.status_code == 401 for response in responses[:10]))
        self.assertEqual(responses[10].status_code, 429)

    @override_settings(AUTH_COOKIE_MODE=True, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
    def test_cookie_authenticated_unsafe_request_requires_matching_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        login = client.post("/api/v1/auth/token", {"username": "mfa-user", "password": "StrongPassword123!"}, format="json")
        self.assertEqual(login.status_code, 200)
        csrf = client.cookies["csrftoken"].value

        missing = client.post("/api/v1/auth/logout", {}, format="json")
        wrong = client.post("/api/v1/auth/logout", {}, format="json", HTTP_X_CSRFTOKEN="0" * 32)
        ok = client.post("/api/v1/auth/logout", {}, format="json", HTTP_X_CSRFTOKEN=csrf)

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(ok.status_code, 200)

    @override_settings(AUTH_COOKIE_MODE=True, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
    def test_cookie_refresh_requires_matching_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        login = client.post("/api/v1/auth/token", {"username": "mfa-user", "password": "StrongPassword123!"}, format="json")
        self.assertEqual(login.status_code, 200)
        csrf = client.cookies["csrftoken"].value

        missing = client.post("/api/v1/auth/token/refresh", {}, format="json")
        ok = client.post("/api/v1/auth/token/refresh", {}, format="json", HTTP_X_CSRFTOKEN=csrf)

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(ok.status_code, 200)

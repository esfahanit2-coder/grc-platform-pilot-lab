from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Tenant, TenantMembership
from .models import UserRoleScope
from .services import bootstrap_tenant_rbac


class TenantMembershipAdministrationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="membership-admin", password="StrongPassword123!")
        self.member = User.objects.create_user(username="membership-user", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Membership Tenant", code="membership-tenant")
        TenantMembership.objects.create(tenant=self.tenant, user=self.admin, role_code="admin")
        self.membership = TenantMembership.objects.create(tenant=self.tenant, user=self.member, role_code="member")
        roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.viewer_role = roles["viewer"]
        self.assignment = UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.member,
            role=self.viewer_role,
            organization_unit=None,
        )
        token = str(RefreshToken.for_user(self.admin).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def test_default_user_list_remains_active_only(self):
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active", "updated_at"])

        response = self.client.get("/api/v1/tenant-users/")

        self.assertEqual(response.status_code, 200)
        usernames = {row["username"] for row in response.data}
        self.assertNotIn(self.member.username, usernames)

    def test_admin_can_include_inactive_memberships_explicitly(self):
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active", "updated_at"])

        response = self.client.get("/api/v1/tenant-users/?include_inactive=true")

        self.assertEqual(response.status_code, 200)
        rows = {row["username"]: row for row in response.data}
        self.assertIn(self.member.username, rows)
        self.assertFalse(rows[self.member.username]["membership_active"])

    def test_deactivation_revokes_active_scopes_and_reactivation_does_not_restore_them(self):
        deactivate = self.client.patch(
            f"/api/v1/tenant-users/{self.member.id}/",
            {"membership_active": False},
            format="json",
        )
        self.assertEqual(deactivate.status_code, 200)
        self.membership.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertFalse(self.membership.is_active)
        self.assertFalse(self.assignment.is_active)

        reactivate = self.client.patch(
            f"/api/v1/tenant-users/{self.member.id}/",
            {"membership_active": True},
            format="json",
        )
        self.assertEqual(reactivate.status_code, 200)
        self.membership.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertTrue(self.membership.is_active)
        self.assertFalse(self.assignment.is_active)

    def test_revoked_role_scope_can_be_explicitly_reassigned_without_duplicate_row(self):
        revoke = self.client.delete(f"/api/v1/role-assignments/{self.assignment.id}/")
        self.assertEqual(revoke.status_code, 204)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_active)

        reassign = self.client.post(
            f"/api/v1/tenant-users/{self.member.id}/role-assignments/",
            {"role_code": self.viewer_role.code, "organization_unit": None},
            format="json",
        )
        self.assertEqual(reassign.status_code, 201)
        self.assignment.refresh_from_db()
        self.assertTrue(self.assignment.is_active)
        self.assertEqual(str(self.assignment.id), reassign.data["id"])
        self.assertEqual(
            UserRoleScope.objects.filter(
                tenant=self.tenant,
                user=self.member,
                role=self.viewer_role,
                organization_unit__isnull=True,
            ).count(),
            1,
        )

    def test_membership_active_requires_boolean_json_value(self):
        response = self.client.patch(
            f"/api/v1/tenant-users/{self.member.id}/",
            {"membership_active": "false"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.is_active)

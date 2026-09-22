from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.services import bootstrap_tenant_rbac
from apps.tenancy.models import Tenant, TenantMembership
from .models import OrganizationUnit


class OrganizationValidationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="bob", password="StrongPassword123!")
        self.a = Tenant.objects.create(name="A", code="a")
        self.b = Tenant.objects.create(name="B", code="b")
        self.foreign_user = User.objects.create_user(username="foreign", password="StrongPassword123!")
        TenantMembership.objects.create(tenant=self.b, user=self.foreign_user)
        TenantMembership.objects.create(tenant=self.a, user=self.user, role_code="admin")
        bootstrap_tenant_rbac(self.a, admin_user=self.user)
        self.foreign_parent = OrganizationUnit.objects.create(tenant=self.b, unit_type="company", code="B", name="B")
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_parent_cannot_cross_tenant_boundary(self):
        response = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "department", "code": "IT", "name": "IT", "parent": str(self.foreign_parent.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.a.id),
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_cross_tenant_boundary(self):
        response = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "department", "code": "SEC", "name": "Security", "manager": self.foreign_user.id},
            format="json",
            HTTP_X_TENANT_ID=str(self.a.id),
        )
        self.assertEqual(response.status_code, 400)

    def test_hierarchy_cycle_is_rejected(self):
        parent = OrganizationUnit.objects.create(tenant=self.a, unit_type="company", code="P", name="Parent")
        child = OrganizationUnit.objects.create(tenant=self.a, parent=parent, unit_type="department", code="C", name="Child")
        response = self.client.patch(
            f"/api/v1/organization-units/{parent.id}/",
            {"parent": str(child.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.a.id),
        )
        self.assertEqual(response.status_code, 400)

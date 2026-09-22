from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.identity.models import UserRoleScope
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership


@override_settings(AUTH_PASSWORD_VALIDATORS=[])
class DatacenterBootstrapCommandTests(TestCase):
    def test_bootstrap_creates_tenant_admin_scope_and_is_idempotent(self):
        output = StringIO()
        password = "Very-Long-Datacenter-Test-Password-123!"
        with patch("sys.stdin", StringIO(password + "\n")):
            call_command(
                "bootstrap_datacenter",
                tenant_code="customer-one",
                tenant_name="Customer One",
                admin_username="root.admin",
                admin_email="root.admin@example.test",
                password_stdin=True,
                json=True,
                stdout=output,
            )

        User = get_user_model()
        tenant = Tenant.objects.get(code="customer-one")
        user = User.objects.get(username="root.admin")
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, output.getvalue())
        self.assertTrue(
            TenantMembership.objects.filter(tenant=tenant, user=user, role_code="admin", is_active=True).exists()
        )
        self.assertTrue(
            UserRoleScope.objects.filter(
                tenant=tenant,
                user=user,
                role__code="tenant_admin",
                organization_unit__isnull=True,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            OrganizationUnit.objects.filter(tenant=tenant, code="customer-one", manager=user).exists()
        )

        second = StringIO()
        call_command(
            "bootstrap_datacenter",
            tenant_code="customer-one",
            tenant_name="Customer One",
            admin_username="root.admin",
            admin_email="root.admin@example.test",
            json=True,
            stdout=second,
        )
        self.assertEqual(Tenant.objects.count(), 1)
        self.assertEqual(User.objects.filter(username="root.admin").count(), 1)
        self.assertIn('"password_changed": false', second.getvalue().lower())

    def test_refuses_unrelated_existing_tenant_by_default(self):
        Tenant.objects.create(name="Existing", code="existing")
        with self.assertRaisesMessage(CommandError, "Another tenant already exists"):
            call_command(
                "bootstrap_datacenter",
                tenant_code="new",
                tenant_name="New",
                admin_username="admin",
                admin_email="admin@example.test",
                json=True,
            )

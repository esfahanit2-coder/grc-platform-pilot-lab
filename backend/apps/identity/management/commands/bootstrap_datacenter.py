from __future__ import annotations

import getpass
import json
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership


class Command(BaseCommand):
    help = "Bootstrap the first datacenter tenant, root organization and tenant administrator without exposing the password."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", required=True)
        parser.add_argument("--tenant-name", required=True)
        parser.add_argument("--admin-username", required=True)
        parser.add_argument("--admin-email", required=True)
        parser.add_argument("--organization-code")
        parser.add_argument("--organization-name")
        parser.add_argument("--password-stdin", action="store_true")
        parser.add_argument("--reset-password", action="store_true")
        parser.add_argument(
            "--allow-existing-tenants",
            action="store_true",
            help="Allow bootstrap in a database that already contains a different tenant.",
        )
        parser.add_argument("--json", action="store_true")

    def _read_password(self, password_stdin: bool) -> str:
        if password_stdin:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = getpass.getpass("Initial administrator password: ")
            confirm = getpass.getpass("Confirm administrator password: ")
            if password != confirm:
                raise CommandError("Password confirmation did not match.")
        if not password:
            raise CommandError("Administrator password cannot be empty.")
        return password

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_code = options["tenant_code"].strip()
        tenant_name = options["tenant_name"].strip()
        username = options["admin_username"].strip()
        email = options["admin_email"].strip().lower()
        organization_code = (options.get("organization_code") or tenant_code).strip()
        organization_name = (options.get("organization_name") or tenant_name).strip()

        if not all([tenant_code, tenant_name, username, email, organization_code, organization_name]):
            raise CommandError("Bootstrap identifiers and names must not be empty.")
        if "@" not in email:
            raise CommandError("Administrator email must be valid.")

        other_tenants = Tenant.objects.exclude(code=tenant_code)
        if other_tenants.exists() and not options["allow_existing_tenants"]:
            raise CommandError(
                "Another tenant already exists. Refusing first-install bootstrap without --allow-existing-tenants."
            )

        tenant, tenant_created = Tenant.objects.get_or_create(
            code=tenant_code,
            defaults={
                "name": tenant_name,
                "tenant_type": Tenant.TenantType.ENTERPRISE,
                "status": "active",
                "default_language": "fa",
                "timezone": "Asia/Tehran",
            },
        )
        if tenant.name != tenant_name:
            raise CommandError("Existing tenant code belongs to a different tenant name.")
        if tenant.status != "active":
            raise CommandError("Existing tenant is not active.")

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
            user_created = False
        except User.DoesNotExist:
            user = User(username=username, email=email, is_active=True)
            user_created = True

        existing_email = (user.email or "").strip().lower()
        if not user_created and existing_email and existing_email != email:
            raise CommandError("Existing administrator username belongs to a different email.")

        needs_password = user_created or options["reset_password"]
        if needs_password:
            password = self._read_password(options["password_stdin"])
            validate_password(password, user=user)
            user.set_password(password)

        user.email = email
        user.is_active = True
        if user_created:
            user.save()
        else:
            fields = ["email", "is_active"]
            if needs_password:
                fields.append("password")
            user.save(update_fields=fields)

        roles = bootstrap_tenant_rbac(tenant, admin_user=user)
        membership, _ = TenantMembership.objects.update_or_create(
            tenant=tenant,
            user=user,
            defaults={"role_code": "admin", "is_active": True},
        )
        UserRoleScope.objects.update_or_create(
            tenant=tenant,
            user=user,
            role=roles["tenant_admin"],
            organization_unit=None,
            defaults={"is_active": True, "valid_from": None, "valid_until": None},
        )

        organization, _ = OrganizationUnit.objects.get_or_create(
            tenant=tenant,
            code=organization_code,
            defaults={
                "name": organization_name,
                "unit_type": OrganizationUnit.UnitType.COMPANY,
                "manager": user,
                "status": "active",
            },
        )
        if organization.name != organization_name:
            raise CommandError("Existing organization code belongs to a different organization name.")
        if organization.manager_id is None:
            organization.manager = user
            organization.save(update_fields=["manager", "updated_at"])

        payload = {
            "schema": "grc-datacenter-bootstrap-v1",
            "tenant_id": str(tenant.id),
            "tenant_code": tenant.code,
            "admin_user_id": str(user.pk),
            "admin_username": user.get_username(),
            "membership_id": str(membership.id),
            "organization_id": str(organization.id),
            "organization_code": organization.code,
            "tenant_created": tenant_created,
            "admin_created": user_created,
            "password_changed": needs_password,
            "password_returned": False,
        }
        if options["json"]:
            self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        else:
            self.stdout.write(self.style.SUCCESS("Datacenter tenant/admin bootstrap completed."))
            self.stdout.write(f"tenant={tenant.code} admin={user.get_username()} organization={organization.code}")
            self.stdout.write("Password was accepted through the protected input path and is not printed or persisted in plaintext.")

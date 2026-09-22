from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.assets.models import Asset
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.internal_audits.models import AuditEngagement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership


class CoreRegisterUxApiTests(APITestCase):
    def setUp(self):
        User=get_user_model()
        self.admin=User.objects.create_user(username="ux-admin",password="StrongPassword123!")
        self.scoped=User.objects.create_user(username="ux-scoped",password="StrongPassword123!")
        self.owner=User.objects.create_user(username="ux-owner",password="StrongPassword123!")
        self.tenant=Tenant.objects.create(name="UX Tenant",code="ux-tenant")
        TenantMembership.objects.create(tenant=self.tenant,user=self.admin,role_code="admin")
        TenantMembership.objects.create(tenant=self.tenant,user=self.scoped,role_code="member")
        TenantMembership.objects.create(tenant=self.tenant,user=self.owner,role_code="member")
        roles=bootstrap_tenant_rbac(self.tenant,admin_user=self.admin)
        self.hq=OrganizationUnit.objects.create(
            tenant=self.tenant,unit_type=OrganizationUnit.UnitType.COMPANY,code="HQ",name="Head Office"
        )
        self.ops=OrganizationUnit.objects.create(
            tenant=self.tenant,unit_type=OrganizationUnit.UnitType.BUSINESS_UNIT,code="OPS",name="Operations"
        )
        UserRoleScope.objects.create(
            user=self.scoped,tenant=self.tenant,role=roles["tenant_admin"],organization_unit=self.hq
        )
        self.asset_hq=Asset.objects.create(
            tenant=self.tenant,organization_unit=self.hq,asset_type=Asset.AssetType.APPLICATION,
            code="APP-1",title="Payroll App",owner=self.owner,status=Asset.Status.ACTIVE
        )
        self.asset_ops=Asset.objects.create(
            tenant=self.tenant,organization_unit=self.ops,asset_type=Asset.AssetType.HARDWARE,
            code="HW-OPS",title="OPS Server",owner=self.owner,status=Asset.Status.ACTIVE
        )
        today=timezone.localdate()
        self.action_overdue=Action.objects.create(
            tenant=self.tenant,organization_unit=self.hq,title="Patch payroll",description="Urgent payroll patch",
            owner=self.owner,priority=Action.Priority.CRITICAL,status=Action.Status.IN_PROGRESS,due_date=today-timedelta(days=1)
        )
        self.action_future=Action.objects.create(
            tenant=self.tenant,organization_unit=self.hq,title="Review access",owner=self.owner,
            priority=Action.Priority.MEDIUM,status=Action.Status.TODO,due_date=today+timedelta(days=3)
        )
        self.audit=AuditEngagement.objects.create(
            tenant=self.tenant,organization_unit=self.hq,title="Payroll audit",audit_type=AuditEngagement.AuditType.INTERNAL,
            objective="Review payroll controls",scope="Payroll",lead_auditor=self.admin,status=AuditEngagement.Status.PLANNED
        )
        AuditEngagement.objects.create(
            tenant=self.tenant,organization_unit=self.hq,title="Follow-up",audit_type=AuditEngagement.AuditType.FOLLOW_UP,
            objective="Follow up",scope="Payroll",lead_auditor=self.admin,status=AuditEngagement.Status.COMPLETED
        )

    def auth(self,user):
        token=str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def test_asset_selector_options_respect_scoped_units_without_membership_view_dependency(self):
        self.auth(self.scoped)
        response=self.client.get("/api/v1/assets/selector-options/")
        self.assertEqual(response.status_code,200)
        unit_codes={row["code"] for row in response.json()["organization_units"]}
        self.assertEqual(unit_codes,{"HQ"})
        usernames={row["username"] for row in response.json()["users"]}
        self.assertIn("ux-owner",usernames)

    def test_asset_register_filters_search_type_and_status(self):
        self.auth(self.admin)
        response=self.client.get("/api/v1/assets/?search=Payroll&asset_type=application&status=active")
        self.assertEqual(response.status_code,200)
        rows=response.json().get("results",response.json())
        self.assertEqual([row["code"] for row in rows],["APP-1"])

    def test_action_filters_support_search_priority_status_and_due(self):
        self.auth(self.admin)
        response=self.client.get("/api/v1/actions/?search=payroll&priority=critical&status=in_progress&due=overdue")
        self.assertEqual(response.status_code,200)
        rows=response.json().get("results",response.json())
        self.assertEqual([row["id"] for row in rows],[str(self.action_overdue.id)])

    def test_action_selector_options_respect_scoped_units(self):
        self.auth(self.scoped)
        response=self.client.get("/api/v1/actions/selector-options/")
        self.assertEqual(response.status_code,200)
        self.assertEqual({row["code"] for row in response.json()["organization_units"]},{"HQ"})

    def test_audit_register_filters_search_type_and_status(self):
        self.auth(self.admin)
        response=self.client.get("/api/v1/audits/?search=Payroll&audit_type=internal&status=planned")
        self.assertEqual(response.status_code,200)
        rows=response.json().get("results",response.json())
        self.assertEqual([row["id"] for row in rows],[str(self.audit.id)])

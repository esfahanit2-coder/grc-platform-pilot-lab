from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.risks.models import Risk, RiskCategory
from apps.tenancy.models import Tenant, TenantMembership

from .models import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowInstance,
    WorkflowState,
    WorkflowTransition,
)
from .services import start_workflow, transition_workflow


User = get_user_model()


class WorkflowScopeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="wf-admin", password="StrongPassword123!"
        )
        self.user = User.objects.create_user(
            username="wf-user", password="StrongPassword123!"
        )
        self.tenant = Tenant.objects.create(name="WF", code="wf")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.admin, role_code="admin"
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role_code="member"
        )
        roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.a = OrganizationUnit.objects.create(
            tenant=self.tenant, unit_type="company", code="A", name="A"
        )
        self.b = OrganizationUnit.objects.create(
            tenant=self.tenant, unit_type="company", code="B", name="B"
        )
        UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=roles["risk_manager"],
            organization_unit=self.a,
        )
        category = RiskCategory.objects.create(
            tenant=self.tenant, code="cyber", name="Cyber"
        )
        self.ra = Risk.objects.create(
            tenant=self.tenant,
            organization_unit=self.a,
            category=category,
            code="RA",
            title="A risk",
            owner=self.user,
        )
        self.rb = Risk.objects.create(
            tenant=self.tenant,
            organization_unit=self.b,
            category=category,
            code="RB",
            title="B risk",
            owner=self.admin,
        )
        self.definition = WorkflowDefinition.objects.create(
            tenant=self.tenant, name="Risk review", object_type="risk"
        )
        self.draft = WorkflowState.objects.create(
            definition=self.definition,
            code="draft",
            name="Draft",
            is_initial=True,
        )
        self.approved = WorkflowState.objects.create(
            definition=self.definition,
            code="approved",
            name="Approved",
            is_terminal=True,
        )
        self.transition = WorkflowTransition.objects.create(
            definition=self.definition,
            code="approve",
            name="Approve",
            from_state=self.draft,
            to_state=self.approved,
            required_permission_code="risk.manage",
        )

    def test_scoped_user_can_start_and_transition_own_unit_workflow(self):
        instance = start_workflow(
            tenant=self.tenant,
            user=self.user,
            definition=self.definition,
            object_type="risk",
            object_id=self.ra.id,
        )
        instance, _ = transition_workflow(
            tenant=self.tenant,
            user=self.user,
            instance=instance,
            transition=self.transition,
        )
        self.assertEqual(instance.status, "completed")

    def test_scoped_user_cannot_start_sibling_workflow(self):
        with self.assertRaises(PermissionDenied):
            start_workflow(
                tenant=self.tenant,
                user=self.user,
                definition=self.definition,
                object_type="risk",
                object_id=self.rb.id,
            )

    def test_foreign_tenant_target_is_cloaked_as_not_found(self):
        other_tenant = Tenant.objects.create(name="WF Other", code="wf-other")
        other_user = User.objects.create_user(
            username="wf-other-user", password="StrongPassword123!"
        )
        TenantMembership.objects.create(
            tenant=other_tenant, user=other_user, role_code="admin"
        )
        other_category = RiskCategory.objects.create(
            tenant=other_tenant, code="other", name="Other"
        )
        other_unit = OrganizationUnit.objects.create(
            tenant=other_tenant, unit_type="company", code="O", name="Other"
        )
        foreign_risk = Risk.objects.create(
            tenant=other_tenant,
            organization_unit=other_unit,
            category=other_category,
            code="FOREIGN",
            title="Foreign risk",
            owner=other_user,
        )

        with self.assertRaisesMessage(
            ValidationError, "Workflow target object was not found."
        ):
            start_workflow(
                tenant=self.tenant,
                user=self.admin,
                definition=self.definition,
                object_type="risk",
                object_id=foreign_risk.id,
            )


class WorkflowExecutionApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="workflow-admin", password="StrongPassword123!"
        )
        self.operator = User.objects.create_user(
            username="workflow-operator", password="StrongPassword123!"
        )
        self.operator2 = User.objects.create_user(
            username="workflow-operator-2", password="StrongPassword123!"
        )
        self.viewer = User.objects.create_user(
            username="workflow-viewer", password="StrongPassword123!"
        )
        self.outsider = User.objects.create_user(
            username="workflow-outsider", password="StrongPassword123!"
        )

        self.tenant = Tenant.objects.create(name="Workflow Tenant", code="workflow-tenant")
        for user, role_code in [
            (self.admin, "admin"),
            (self.operator, "member"),
            (self.operator2, "member"),
            (self.viewer, "member"),
        ]:
            TenantMembership.objects.create(
                tenant=self.tenant, user=user, role_code=role_code
            )

        self.other_tenant = Tenant.objects.create(
            name="Other Workflow Tenant", code="other-workflow"
        )
        TenantMembership.objects.create(
            tenant=self.other_tenant, user=self.outsider, role_code="member"
        )

        roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type="department",
            code="GRC",
            name="GRC",
        )
        for user in (self.operator, self.operator2):
            UserRoleScope.objects.create(
                tenant=self.tenant,
                user=user,
                role=roles["risk_manager"],
                organization_unit=self.unit,
            )
        UserRoleScope.objects.create(
            tenant=self.tenant,
            user=self.viewer,
            role=roles["viewer"],
            organization_unit=self.unit,
        )

        category = RiskCategory.objects.create(
            tenant=self.tenant, code="ops", name="Operational"
        )
        self.risk = Risk.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            category=category,
            code="R-001",
            title="Workflow execution risk",
            owner=self.operator,
        )

        self.definition = WorkflowDefinition.objects.create(
            tenant=self.tenant,
            name="Risk approval",
            object_type="risk",
        )
        self.draft = WorkflowState.objects.create(
            definition=self.definition,
            code="draft",
            name="Draft",
            is_initial=True,
            sort_order=1,
        )
        self.review = WorkflowState.objects.create(
            definition=self.definition,
            code="review",
            name="Review",
            sort_order=2,
        )
        self.done = WorkflowState.objects.create(
            definition=self.definition,
            code="done",
            name="Done",
            is_terminal=True,
            sort_order=3,
        )
        self.submit_transition = WorkflowTransition.objects.create(
            definition=self.definition,
            code="submit",
            name="Submit for review",
            from_state=self.draft,
            to_state=self.review,
            required_permission_code="risk.manage",
        )
        self.close_transition = WorkflowTransition.objects.create(
            definition=self.definition,
            code="close",
            name="Close",
            from_state=self.review,
            to_state=self.done,
            required_permission_code="risk.manage",
        )
        self.instance = start_workflow(
            tenant=self.tenant,
            user=self.operator,
            definition=self.definition,
            object_type="risk",
            object_id=self.risk.id,
        )
        self.auth(self.operator)

    def auth(self, user, tenant=None):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str((tenant or self.tenant).id),
        )

    def test_available_transitions_are_permission_aware(self):
        response = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/available-transitions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["code"] for row in response.data], ["submit"])

        self.auth(self.viewer)
        viewer_response = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/available-transitions/"
        )
        self.assertEqual(viewer_response.status_code, 200)
        self.assertEqual(viewer_response.data, [])

    def test_viewer_can_read_visible_instance_but_cannot_mutate(self):
        self.auth(self.viewer)
        detail = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/"
        )
        assigned = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/assign/",
            {"assignee_id": self.viewer.id},
            format="json",
        )
        transitioned = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {"transition_id": str(self.submit_transition.id)},
            format="json",
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(assigned.status_code, 403)
        self.assertEqual(transitioned.status_code, 403)

    def test_assignee_candidates_are_minimal_and_actionable(self):
        response = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/assignee-candidates/"
        )
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.operator.id, ids)
        self.assertIn(self.operator2.id, ids)
        self.assertNotIn(self.viewer.id, ids)
        self.assertNotIn(self.outsider.id, ids)
        self.assertTrue(
            all(
                set(row) == {"id", "username", "display"}
                for row in response.data["results"]
            )
        )

    def test_assign_and_unassign_are_audited_history(self):
        assigned = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/assign/",
            {
                "assignee_id": self.operator2.id,
                "comment": "Route to second operator",
            },
            format="json",
        )
        self.assertEqual(assigned.status_code, 200)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.assigned_to_id, self.operator2.id)

        event = WorkflowEvent.objects.filter(
            instance=self.instance,
            metadata__event_type="assignment",
        ).latest("created_at")
        self.assertEqual(event.metadata["assignee_id"], self.operator2.id)
        self.assertEqual(event.comment, "Route to second operator")
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="workflow.assign",
                object_type="workflow_instance",
                object_id=self.instance.id,
            ).exists()
        )

        unassigned = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/assign/",
            {"assignee_id": None, "comment": "Back to shared queue"},
            format="json",
        )
        self.assertEqual(unassigned.status_code, 200)
        self.instance.refresh_from_db()
        self.assertIsNone(self.instance.assigned_to_id)

    def test_non_actionable_and_cross_tenant_assignees_are_rejected(self):
        viewer_response = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/assign/",
            {"assignee_id": self.viewer.id},
            format="json",
        )
        outsider_response = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/assign/",
            {"assignee_id": self.outsider.id},
            format="json",
        )

        self.assertEqual(viewer_response.status_code, 400)
        self.assertEqual(outsider_response.status_code, 400)
        self.instance.refresh_from_db()
        self.assertIsNone(self.instance.assigned_to_id)

    def test_assignment_never_grants_transition_authority(self):
        WorkflowInstance.objects.filter(id=self.instance.id).update(
            assigned_to=self.viewer
        )
        self.auth(self.viewer)
        response = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {"transition_id": str(self.submit_transition.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.current_state_id, self.draft.id)

    def test_transition_history_is_enriched_and_replay_is_rejected(self):
        response = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {
                "transition_id": str(self.submit_transition.id),
                "comment": "Ready for review",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        replay = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {"transition_id": str(self.submit_transition.id)},
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

        history = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/events/"
        )
        self.assertEqual(history.status_code, 200)
        transition_events = [
            row for row in history.data if row["event_type"] == "transition"
        ]
        self.assertEqual(len(transition_events), 1)
        event = transition_events[0]
        self.assertEqual(event["transition_name"], "Submit for review")
        self.assertEqual(event["from_state_detail"]["code"], "draft")
        self.assertEqual(event["to_state_detail"]["code"], "review")
        self.assertEqual(event["comment"], "Ready for review")
        self.assertEqual(event["actor_display"], self.operator.get_username())

    def test_terminal_instance_has_no_available_transition(self):
        first = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {"transition_id": str(self.submit_transition.id)},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            f"/api/v1/workflows/instances/{self.instance.id}/transition/",
            {"transition_id": str(self.close_transition.id)},
            format="json",
        )
        self.assertEqual(second.status_code, 200)

        available = self.client.get(
            f"/api/v1/workflows/instances/{self.instance.id}/available-transitions/"
        )
        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.data, [])
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, "completed")

    def test_assigned_to_me_filter_returns_only_my_work(self):
        WorkflowInstance.objects.filter(id=self.instance.id).update(
            assigned_to=self.operator
        )
        response = self.client.get(
            "/api/v1/workflows/instances/?assigned_to=me"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        self.assertEqual(
            [str(row["id"]) for row in rows],
            [str(self.instance.id)],
        )

    def test_workflow_configuration_mutations_are_audited(self):
        self.auth(self.admin)
        created = self.client.post(
            "/api/v1/workflows/definitions/",
            {"name": "Audited definition", "object_type": "risk", "version": 1},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        definition_id = created.data["id"]

        updated = self.client.patch(
            f"/api/v1/workflows/definitions/{definition_id}/",
            {"name": "Audited definition v2"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)

        state = self.client.post(
            f"/api/v1/workflows/definitions/{definition_id}/states/",
            {"code": "draft", "name": "Draft", "is_initial": True},
            format="json",
        )
        self.assertEqual(state.status_code, 201)

        state2 = self.client.post(
            f"/api/v1/workflows/definitions/{definition_id}/states/",
            {"code": "done", "name": "Done", "is_terminal": True},
            format="json",
        )
        self.assertEqual(state2.status_code, 201)

        transition = self.client.post(
            f"/api/v1/workflows/definitions/{definition_id}/transitions/",
            {
                "code": "finish",
                "name": "Finish",
                "from_state": state.data["id"],
                "to_state": state2.data["id"],
                "required_permission_code": "workflow.transition",
            },
            format="json",
        )
        self.assertEqual(transition.status_code, 201)

        deleted = self.client.delete(
            f"/api/v1/workflows/definitions/{definition_id}/"
        )
        self.assertEqual(deleted.status_code, 204)

        actions = set(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                object_type__in=[
                    "workflow_definition",
                    "workflow_state",
                    "workflow_transition",
                ],
            ).values_list("action", flat=True)
        )
        self.assertTrue(
            {
                "workflow.definition.create",
                "workflow.definition.update",
                "workflow.state.create",
                "workflow.transition.create",
                "workflow.definition.delete",
            }.issubset(actions)
        )

    def test_foreign_tenant_instance_is_hidden(self):
        other_unit = OrganizationUnit.objects.create(
            tenant=self.other_tenant,
            unit_type="department",
            code="OTHER",
            name="Other",
        )
        other_category = RiskCategory.objects.create(
            tenant=self.other_tenant,
            code="other",
            name="Other",
        )
        other_risk = Risk.objects.create(
            tenant=self.other_tenant,
            organization_unit=other_unit,
            category=other_category,
            code="OR-1",
            title="Other tenant risk",
            owner=self.outsider,
        )
        other_definition = WorkflowDefinition.objects.create(
            tenant=self.other_tenant,
            name="Other flow",
            object_type="risk",
        )
        other_state = WorkflowState.objects.create(
            definition=other_definition,
            code="draft",
            name="Draft",
            is_initial=True,
        )
        foreign_instance = WorkflowInstance.objects.create(
            tenant=self.other_tenant,
            definition=other_definition,
            object_type="risk",
            object_id=other_risk.id,
            organization_unit=other_unit,
            current_state=other_state,
            started_by=self.outsider,
        )

        response = self.client.get(
            f"/api/v1/workflows/instances/{foreign_instance.id}/"
        )
        self.assertEqual(response.status_code, 404)

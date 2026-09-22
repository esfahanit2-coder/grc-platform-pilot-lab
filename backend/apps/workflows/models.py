from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant


class WorkflowDefinition(UUIDTimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="workflow_definitions")
    name = models.CharField(max_length=160)
    object_type = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "version"],
                name="uq_workflow_tenant_name_version",
            )
        ]
        indexes = [models.Index(fields=["tenant", "object_type", "is_active"])]


class WorkflowState(UUIDTimeStampedModel):
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE, related_name="states"
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "code"], name="uq_workflow_state_code"
            )
        ]
        ordering = ["sort_order", "code"]


class WorkflowTransition(UUIDTimeStampedModel):
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE, related_name="transitions"
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    from_state = models.ForeignKey(
        WorkflowState, on_delete=models.CASCADE, related_name="outgoing_transitions"
    )
    to_state = models.ForeignKey(
        WorkflowState, on_delete=models.CASCADE, related_name="incoming_transitions"
    )
    required_permission_code = models.CharField(max_length=120, blank=True)
    condition = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "code"], name="uq_workflow_transition_code"
            )
        ]


class WorkflowInstance(UUIDTimeStampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="workflow_instances"
    )
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT, related_name="instances"
    )
    object_type = models.CharField(max_length=80)
    object_id = models.UUIDField()
    organization_unit = models.ForeignKey(
        OrganizationUnit,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="workflow_instances",
    )
    current_state = models.ForeignKey(
        WorkflowState, on_delete=models.PROTECT, related_name="instances"
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="started_workflows",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_workflow_instances",
    )
    status = models.CharField(max_length=20, default="active")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "definition", "object_type", "object_id"],
                name="uq_workflow_instance_object",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "object_type", "object_id"]),
            models.Index(fields=["tenant", "current_state"]),
            models.Index(
                fields=["tenant", "assigned_to", "status"],
                name="wf_inst_assignee_status_idx",
            ),
        ]


class WorkflowEvent(UUIDTimeStampedModel):
    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE, related_name="events"
    )
    transition = models.ForeignKey(
        WorkflowTransition,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    from_state = models.ForeignKey(
        WorkflowState,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    to_state = models.ForeignKey(
        WorkflowState, on_delete=models.PROTECT, related_name="+"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workflow_events",
    )
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

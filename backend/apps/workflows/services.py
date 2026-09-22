from django.apps import apps
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_event
from apps.identity.services import (
    has_tenant_permission,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.tenancy.models import TenantMembership

from .models import WorkflowEvent, WorkflowInstance, WorkflowTransition


OBJECT_MODEL_MAP = {
    "risk": ("risks", "Risk"),
    "assessment": ("assessments", "Assessment"),
    "finding": ("findings", "Finding"),
    "document": ("documents", "Document"),
    "action": ("actions", "Action"),
    "audit": ("internal_audits", "AuditEngagement"),
}


def _has_scoped_permission(user, tenant, permission_code, unit):
    if unit is None:
        return has_whole_tenant_permission(user, tenant, permission_code)
    return has_tenant_permission(user, tenant, permission_code, unit)


def _require_scoped_permission(user, tenant, permission_code, unit):
    if unit is None:
        return require_whole_tenant_permission(user, tenant, permission_code)
    return require_tenant_permission(user, tenant, permission_code, unit)


def resolve_workflow_object(tenant, object_type, object_id):
    spec = OBJECT_MODEL_MAP.get(object_type)
    if not spec:
        raise ValidationError("Unsupported workflow object type.")
    model = apps.get_model(*spec)
    queryset = model.objects.filter(id=object_id)
    # Tenant-aware objects are cloaked at the query boundary so callers cannot
    # distinguish a foreign UUID from a missing UUID.
    if any(field.name == "tenant" for field in model._meta.fields):
        queryset = queryset.filter(tenant=tenant)
    if hasattr(model, "deleted_at"):
        queryset = queryset.filter(deleted_at__isnull=True)
    obj = queryset.first()
    if not obj:
        raise ValidationError("Workflow target object was not found.")
    return obj


def workflow_object_label(obj, object_type, object_id):
    code = str(getattr(obj, "code", "") or "").strip()
    title = str(
        getattr(obj, "title", "")
        or getattr(obj, "name", "")
        or getattr(obj, "subject", "")
        or ""
    ).strip()
    if code and title:
        return f"{code} · {title}"
    if title:
        return title
    if code:
        return code
    return f"{object_type} / {str(object_id)[:8]}"


def workflow_target_display(instance):
    cached = str((instance.metadata or {}).get("target_display", "")).strip()
    if cached:
        return cached
    try:
        obj = resolve_workflow_object(
            instance.tenant, instance.object_type, instance.object_id
        )
    except ValidationError:
        return f"{instance.object_type} / {str(instance.object_id)[:8]}"
    return workflow_object_label(obj, instance.object_type, instance.object_id)


def object_scope(tenant, object_type, object_id):
    obj = resolve_workflow_object(tenant, object_type, object_id)
    return getattr(obj, "organization_unit", None)


def current_transitions(instance):
    if instance.status != "active":
        return []
    return list(
        WorkflowTransition.objects.filter(
            definition=instance.definition,
            from_state=instance.current_state,
            deleted_at__isnull=True,
            to_state__deleted_at__isnull=True,
        )
        .select_related("from_state", "to_state")
        .order_by("to_state__sort_order", "name", "code")
    )


def available_transitions_for_user(*, tenant, user, instance, transitions=None):
    candidates = current_transitions(instance) if transitions is None else transitions
    return [
        transition
        for transition in candidates
        if _has_scoped_permission(
            user,
            tenant,
            transition.required_permission_code or "workflow.transition",
            instance.organization_unit,
        )
    ]


def can_assign_workflow(*, tenant, user, instance):
    return instance.status == "active" and _has_scoped_permission(
        user, tenant, "workflow.transition", instance.organization_unit
    )


def can_user_act_on_instance(
    *, tenant, user, instance, transitions=None, membership_verified=False
):
    if not membership_verified and not TenantMembership.objects.filter(
        tenant=tenant, user=user, is_active=True
    ).exists():
        return False
    if not _has_scoped_permission(
        user, tenant, "workflow.view", instance.organization_unit
    ):
        return False
    return bool(
        available_transitions_for_user(
            tenant=tenant,
            user=user,
            instance=instance,
            transitions=transitions,
        )
    )


def start_workflow(
    *, tenant, user, definition, object_type, object_id, request=None
):
    if definition.tenant_id != tenant.id or not definition.is_active:
        raise ValidationError("Invalid workflow definition.")
    if definition.object_type != object_type:
        raise ValidationError("Workflow definition does not match object type.")
    initial = (
        definition.states.filter(is_initial=True, deleted_at__isnull=True)
        .order_by("sort_order", "code")
        .first()
    )
    if not initial:
        raise ValidationError("Workflow has no initial state.")

    target = resolve_workflow_object(tenant, object_type, object_id)
    unit = getattr(target, "organization_unit", None)
    _require_scoped_permission(user, tenant, "workflow.start", unit)
    target_display = workflow_object_label(target, object_type, object_id)

    instance, created = WorkflowInstance.objects.get_or_create(
        tenant=tenant,
        definition=definition,
        object_type=object_type,
        object_id=object_id,
        defaults={
            "organization_unit": unit,
            "current_state": initial,
            "started_by": user,
            "status": "active",
            "metadata": {"target_display": target_display},
        },
    )
    if created:
        WorkflowEvent.objects.create(
            instance=instance,
            to_state=initial,
            actor=user,
            comment="Workflow started",
            metadata={"event_type": "started"},
        )
        record_audit_event(
            user,
            tenant,
            "workflow.start",
            "workflow_instance",
            instance.id,
            metadata={"object_type": object_type, "object_id": str(object_id)},
            request=request,
        )
    return instance


@transaction.atomic
def assign_workflow(
    *, tenant, user, instance, assignee=None, comment="", request=None
):
    instance = (
        WorkflowInstance.objects.select_for_update(of=("self",))
        .select_related(
            "current_state",
            "organization_unit",
            "definition",
            "assigned_to",
        )
        .get(id=instance.id, tenant=tenant)
    )
    if instance.status != "active":
        raise ValidationError("Workflow is not active.")
    _require_scoped_permission(
        user, tenant, "workflow.transition", instance.organization_unit
    )

    transitions = current_transitions(instance)
    if assignee is not None and not can_user_act_on_instance(
        tenant=tenant,
        user=assignee,
        instance=instance,
        transitions=transitions,
    ):
        raise ValidationError(
            {"assignee_id": "Assignee is not an active actionable member in this workflow scope."}
        )

    previous = instance.assigned_to
    if previous and assignee and previous.id == assignee.id:
        return instance, None
    if previous is None and assignee is None:
        return instance, None

    instance.assigned_to = assignee
    instance.save(update_fields=["assigned_to", "updated_at"])

    previous_display = (
        previous.get_full_name() or previous.get_username() if previous else ""
    )
    assignee_display = (
        assignee.get_full_name() or assignee.get_username() if assignee else ""
    )
    event = WorkflowEvent.objects.create(
        instance=instance,
        from_state=instance.current_state,
        to_state=instance.current_state,
        actor=user,
        comment=comment,
        metadata={
            "event_type": "assignment",
            "previous_assignee_id": previous.id if previous else None,
            "previous_assignee_display": previous_display,
            "assignee_id": assignee.id if assignee else None,
            "assignee_display": assignee_display,
        },
    )
    record_audit_event(
        user,
        tenant,
        "workflow.assign",
        "workflow_instance",
        instance.id,
        metadata={
            "previous_assignee_id": previous.id if previous else None,
            "assignee_id": assignee.id if assignee else None,
        },
        request=request,
    )
    return instance, event


@transaction.atomic
def transition_workflow(
    *, tenant, user, instance, transition, comment="", request=None
):
    instance = (
        WorkflowInstance.objects.select_for_update(of=("self",))
        .select_related("current_state", "organization_unit")
        .get(id=instance.id, tenant=tenant)
    )
    if instance.status != "active":
        raise ValidationError("Workflow is not active.")
    if transition.deleted_at is not None:
        raise ValidationError("Transition is not available.")
    if (
        transition.definition_id != instance.definition_id
        or transition.from_state_id != instance.current_state_id
    ):
        raise ValidationError("Transition is not allowed from the current state.")

    code = transition.required_permission_code or "workflow.transition"
    _require_scoped_permission(user, tenant, code, instance.organization_unit)

    previous = instance.current_state
    instance.current_state = transition.to_state
    if transition.to_state.is_terminal:
        instance.status = "completed"
    instance.save(update_fields=["current_state", "status", "updated_at"])

    event = WorkflowEvent.objects.create(
        instance=instance,
        transition=transition,
        from_state=previous,
        to_state=transition.to_state,
        actor=user,
        comment=comment,
        metadata={"event_type": "transition"},
    )
    record_audit_event(
        user,
        tenant,
        "workflow.transition",
        "workflow_instance",
        instance.id,
        metadata={
            "transition": transition.code,
            "from": previous.code,
            "to": transition.to_state.code,
        },
        request=request,
    )
    return instance, event

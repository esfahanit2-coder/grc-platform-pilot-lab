from rest_framework import serializers

from .models import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowInstance,
    WorkflowState,
    WorkflowTransition,
)
from .services import can_assign_workflow, workflow_target_display


def _display_user(user):
    if not user:
        return ""
    return user.get_full_name() or user.get_username()


class WorkflowStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowState
        fields = [
            "id",
            "code",
            "name",
            "is_initial",
            "is_terminal",
            "sort_order",
            "metadata",
        ]


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTransition
        fields = [
            "id",
            "code",
            "name",
            "from_state",
            "to_state",
            "required_permission_code",
            "condition",
            "actions",
        ]


class WorkflowExecutableTransitionSerializer(serializers.ModelSerializer):
    to_state_detail = WorkflowStateSerializer(source="to_state", read_only=True)

    class Meta:
        model = WorkflowTransition
        fields = ["id", "code", "name", "to_state_detail"]


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    states = WorkflowStateSerializer(many=True, read_only=True)
    transitions = WorkflowTransitionSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = [
            "id",
            "name",
            "object_type",
            "version",
            "is_active",
            "configuration",
            "states",
            "transitions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    current_state_detail = WorkflowStateSerializer(
        source="current_state", read_only=True
    )
    definition_name = serializers.CharField(source="definition.name", read_only=True)
    definition_version = serializers.IntegerField(
        source="definition.version", read_only=True
    )
    organization_unit_name = serializers.CharField(
        source="organization_unit.name", read_only=True
    )
    assigned_to_display = serializers.SerializerMethodField()
    started_by_display = serializers.SerializerMethodField()
    target_display = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()
    can_assign = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowInstance
        fields = [
            "id",
            "definition",
            "definition_name",
            "definition_version",
            "object_type",
            "object_id",
            "target_display",
            "organization_unit",
            "organization_unit_name",
            "current_state",
            "current_state_detail",
            "started_by",
            "started_by_display",
            "assigned_to",
            "assigned_to_display",
            "is_assigned_to_me",
            "can_assign",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assigned_to_display(self, instance):
        return _display_user(instance.assigned_to)

    def get_started_by_display(self, instance):
        return _display_user(instance.started_by)

    def get_target_display(self, instance):
        return workflow_target_display(instance)

    def get_is_assigned_to_me(self, instance):
        request = self.context.get("request")
        return bool(
            request
            and getattr(request.user, "is_authenticated", False)
            and instance.assigned_to_id == request.user.id
        )

    def get_can_assign(self, instance):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return can_assign_workflow(
            tenant=self.context["tenant"],
            user=request.user,
            instance=instance,
        )


class WorkflowEventSerializer(serializers.ModelSerializer):
    actor_display = serializers.SerializerMethodField()
    transition_name = serializers.CharField(source="transition.name", read_only=True)
    from_state_detail = WorkflowStateSerializer(source="from_state", read_only=True)
    to_state_detail = WorkflowStateSerializer(source="to_state", read_only=True)
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowEvent
        fields = [
            "id",
            "event_type",
            "transition",
            "transition_name",
            "from_state",
            "from_state_detail",
            "to_state",
            "to_state_detail",
            "actor",
            "actor_display",
            "comment",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_display(self, event):
        return _display_user(event.actor) or "سیستم"

    def get_event_type(self, event):
        configured = str((event.metadata or {}).get("event_type", "")).strip()
        if configured:
            return configured
        if event.transition_id:
            return "transition"
        if event.from_state_id == event.to_state_id and event.from_state_id:
            return "assignment"
        return "started"

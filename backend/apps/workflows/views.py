from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.tenancy.models import TenantMembership
from apps.tenancy.services import resolve_tenant_for_request

from .models import WorkflowDefinition, WorkflowInstance, WorkflowState, WorkflowTransition
from .serializers import (
    WorkflowDefinitionSerializer,
    WorkflowEventSerializer,
    WorkflowExecutableTransitionSerializer,
    WorkflowInstanceSerializer,
)
from .services import (
    assign_workflow,
    available_transitions_for_user,
    can_assign_workflow,
    can_user_act_on_instance,
    current_transitions,
    start_workflow,
    transition_workflow,
)


class TenantMixin:
    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self._tenant()
        return context


class WorkflowDefinitionViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = WorkflowDefinitionSerializer

    def get_queryset(self):
        tenant = self._tenant()
        permission = (
            "workflow.manage"
            if self.action not in {"list", "retrieve"}
            else "workflow.view"
        )
        require_whole_tenant_permission(self.request.user, tenant, permission)
        return (
            WorkflowDefinition.objects.filter(
                tenant=tenant, deleted_at__isnull=True
            )
            .prefetch_related("states", "transitions")
            .order_by("name", "-version")
        )

    def perform_create(self, serializer):
        instance = serializer.save(tenant=self._tenant())
        record_audit_event(
            self.request.user,
            self._tenant(),
            "workflow.definition.create",
            "workflow_definition",
            instance.id,
            metadata={"name": instance.name, "object_type": instance.object_type},
            request=self.request,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        record_audit_event(
            self.request.user,
            self._tenant(),
            "workflow.definition.update",
            "workflow_definition",
            instance.id,
            metadata={"name": instance.name, "object_type": instance.object_type},
            request=self.request,
        )

    def perform_destroy(self, instance):
        from django.utils import timezone

        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active", "updated_at"])
        record_audit_event(
            self.request.user,
            self._tenant(),
            "workflow.definition.delete",
            "workflow_definition",
            instance.id,
            metadata={"name": instance.name, "object_type": instance.object_type},
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="states")
    def add_state(self, request, pk=None):
        definition = self.get_object()
        require_whole_tenant_permission(
            request.user, self._tenant(), "workflow.manage"
        )
        state = WorkflowState.objects.create(
            definition=definition,
            code=request.data.get("code", ""),
            name=request.data.get("name", ""),
            is_initial=bool(request.data.get("is_initial")),
            is_terminal=bool(request.data.get("is_terminal")),
            sort_order=int(request.data.get("sort_order", 0)),
            metadata=request.data.get("metadata") or {},
        )
        if state.is_initial:
            definition.states.exclude(id=state.id).update(is_initial=False)
        record_audit_event(
            request.user,
            self._tenant(),
            "workflow.state.create",
            "workflow_state",
            state.id,
            metadata={
                "definition_id": str(definition.id),
                "code": state.code,
                "is_initial": state.is_initial,
                "is_terminal": state.is_terminal,
            },
            request=request,
        )
        return Response({"id": str(state.id), "code": state.code}, status=201)

    @action(detail=True, methods=["post"], url_path="transitions")
    def add_transition(self, request, pk=None):
        definition = self.get_object()
        require_whole_tenant_permission(
            request.user, self._tenant(), "workflow.manage"
        )
        from_state = definition.states.filter(
            id=request.data.get("from_state")
        ).first()
        to_state = definition.states.filter(id=request.data.get("to_state")).first()
        if not from_state or not to_state:
            raise ValidationError("States must belong to this workflow.")
        row = WorkflowTransition.objects.create(
            definition=definition,
            code=request.data.get("code", ""),
            name=request.data.get("name", ""),
            from_state=from_state,
            to_state=to_state,
            required_permission_code=request.data.get(
                "required_permission_code", ""
            ),
            condition=request.data.get("condition") or {},
            actions=request.data.get("actions") or [],
        )
        record_audit_event(
            request.user,
            self._tenant(),
            "workflow.transition.create",
            "workflow_transition",
            row.id,
            metadata={
                "definition_id": str(definition.id),
                "code": row.code,
                "from_state": from_state.code,
                "to_state": to_state.code,
                "required_permission_code": row.required_permission_code,
            },
            request=request,
        )
        return Response({"id": str(row.id), "code": row.code}, status=201)


class WorkflowInstanceViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkflowInstanceSerializer

    def get_queryset(self):
        tenant = self._tenant()
        require_tenant_permission(self.request.user, tenant, "workflow.view")
        queryset = (
            WorkflowInstance.objects.filter(
                tenant=tenant, deleted_at__isnull=True
            )
            .select_related(
                "definition",
                "current_state",
                "organization_unit",
                "started_by",
                "assigned_to",
            )
            .order_by("-updated_at")
        )
        if not has_whole_tenant_permission(
            self.request.user, tenant, "workflow.view"
        ):
            allowed = accessible_organization_unit_ids(
                self.request.user, tenant, "workflow.view"
            )
            queryset = queryset.filter(organization_unit_id__in=allowed)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        object_type = self.request.query_params.get("object_type")
        if object_type:
            queryset = queryset.filter(object_type=object_type)

        definition_id = self.request.query_params.get("definition")
        if definition_id:
            queryset = queryset.filter(definition_id=definition_id)

        assigned_to = self.request.query_params.get("assigned_to")
        if assigned_to == "me":
            queryset = queryset.filter(assigned_to=self.request.user)
        elif assigned_to == "unassigned":
            queryset = queryset.filter(assigned_to__isnull=True)
        elif assigned_to:
            try:
                assigned_id = int(assigned_to)
            except (TypeError, ValueError):
                raise ValidationError(
                    {"assigned_to": "Expected me, unassigned or a numeric user id."}
                )
            queryset = queryset.filter(assigned_to_id=assigned_id)
        return queryset

    @action(detail=False, methods=["post"])
    def start(self, request):
        tenant = self._tenant()
        definition = WorkflowDefinition.objects.filter(
            tenant=tenant,
            id=request.data.get("definition_id"),
            deleted_at__isnull=True,
        ).first()
        if not definition:
            raise ValidationError("Workflow definition not found.")
        object_type = str(request.data.get("object_type", "")).strip()
        object_id = request.data.get("object_id")
        if not object_type or not object_id:
            raise ValidationError("object_type and object_id are required.")
        instance = start_workflow(
            tenant=tenant,
            user=request.user,
            definition=definition,
            object_type=object_type,
            object_id=object_id,
            request=request,
        )
        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="available-transitions",
    )
    def available_transitions(self, request, pk=None):
        instance = self.get_object()
        transitions = available_transitions_for_user(
            tenant=self._tenant(),
            user=request.user,
            instance=instance,
        )
        return Response(
            WorkflowExecutableTransitionSerializer(
                transitions, many=True
            ).data
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="assignee-candidates",
    )
    def assignee_candidates(self, request, pk=None):
        instance = self.get_object()
        tenant = self._tenant()
        if not can_assign_workflow(
            tenant=tenant, user=request.user, instance=instance
        ):
            raise PermissionDenied(
                "You do not have permission to route this workflow."
            )

        transitions = current_transitions(instance)
        memberships = list(
            TenantMembership.objects.filter(tenant=tenant, is_active=True)
            .select_related("user")
            .order_by("user__username")[:501]
        )
        truncated = len(memberships) > 500
        results = []
        for membership in memberships[:500]:
            candidate = membership.user
            if not can_user_act_on_instance(
                tenant=tenant,
                user=candidate,
                instance=instance,
                transitions=transitions,
                membership_verified=True,
            ):
                continue
            results.append(
                {
                    "id": candidate.id,
                    "username": candidate.get_username(),
                    "display": candidate.get_full_name()
                    or candidate.get_username(),
                }
            )
        return Response({"results": results, "truncated": truncated})

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        instance = self.get_object()
        tenant = self._tenant()
        assignee = None
        assignee_id = request.data.get("assignee_id")
        if assignee_id not in (None, ""):
            membership = (
                TenantMembership.objects.filter(
                    tenant=tenant,
                    user_id=assignee_id,
                    is_active=True,
                )
                .select_related("user")
                .first()
            )
            if not membership:
                raise ValidationError(
                    {"assignee_id": "Assignee must be an active tenant member."}
                )
            assignee = membership.user

        instance, event = assign_workflow(
            tenant=tenant,
            user=request.user,
            instance=instance,
            assignee=assignee,
            comment=str(request.data.get("comment", "")),
            request=request,
        )
        payload = {"instance": self.get_serializer(instance).data}
        if event is not None:
            payload["event"] = WorkflowEventSerializer(event).data
        return Response(payload)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        instance = self.get_object()
        transition = (
            WorkflowTransition.objects.filter(
                definition=instance.definition,
                id=request.data.get("transition_id"),
                deleted_at__isnull=True,
            )
            .select_related("from_state", "to_state")
            .first()
        )
        if not transition:
            raise ValidationError("Transition not found.")
        instance, event = transition_workflow(
            tenant=self._tenant(),
            user=request.user,
            instance=instance,
            transition=transition,
            comment=str(request.data.get("comment", "")),
            request=request,
        )
        return Response(
            {
                "instance": self.get_serializer(instance).data,
                "event": WorkflowEventSerializer(event).data,
            }
        )

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        events = (
            self.get_object()
            .events.select_related(
                "transition", "from_state", "to_state", "actor"
            )
            .order_by("created_at")
        )
        return Response(
            WorkflowEventSerializer(events, many=True).data
        )

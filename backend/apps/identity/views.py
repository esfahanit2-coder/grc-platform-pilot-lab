from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.tenancy.models import TenantMembership
from apps.tenancy.services import resolve_tenant_for_request
from .models import Permission, Role, UserRoleScope
from .serializers import (
    PermissionSerializer,
    RoleAssignmentSerializer,
    RoleSerializer,
    TenantUserCreateSerializer,
    TenantUserSerializer,
)
from .services import bootstrap_tenant_rbac, require_tenant_permission, require_whole_tenant_permission

User = get_user_model()


class PermissionListView(generics.ListAPIView):
    serializer_class = PermissionSerializer

    def get_queryset(self):
        tenant = resolve_tenant_for_request(self.request)
        require_whole_tenant_permission(self.request.user, tenant, "role.view")
        bootstrap_tenant_rbac(tenant)
        return Permission.objects.filter(is_active=True).order_by("module", "code")


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer

    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant

    def get_queryset(self):
        tenant = self._tenant()
        require_whole_tenant_permission(self.request.user, tenant, "role.view" if self.action in {"list", "retrieve"} else "role.manage")
        bootstrap_tenant_rbac(tenant)
        return Role.objects.filter(tenant=tenant, deleted_at__isnull=True).prefetch_related("permissions").order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self._tenant()
        return context

    def perform_create(self, serializer):
        tenant = self._tenant()
        require_whole_tenant_permission(self.request.user, tenant, "role.manage")
        role = serializer.save()
        record_audit_event(self.request.user, tenant, "role.create", "role", role.id, new_data={"code": role.code, "name": role.name}, request=self.request)

    def perform_update(self, serializer):
        tenant = self._tenant()
        require_whole_tenant_permission(self.request.user, tenant, "role.manage")
        old = {"code": serializer.instance.code, "name": serializer.instance.name, "is_active": serializer.instance.is_active}
        role = serializer.save()
        record_audit_event(self.request.user, tenant, "role.update", "role", role.id, old_data=old, new_data={"code": role.code, "name": role.name, "is_active": role.is_active}, request=self.request)

    def perform_destroy(self, instance):
        tenant = self._tenant()
        require_whole_tenant_permission(self.request.user, tenant, "role.manage")
        if instance.is_system:
            raise ValidationError("System roles cannot be deleted.")
        from django.utils import timezone
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active", "updated_at"])
        record_audit_event(self.request.user, tenant, "role.archive", "role", instance.id, request=self.request)


class TenantUserViewSet(viewsets.ViewSet):
    def _tenant(self, permission):
        tenant = resolve_tenant_for_request(self.request)
        require_whole_tenant_permission(self.request.user, tenant, permission)
        return tenant

    def list(self, request):
        tenant = self._tenant("membership.view")
        include_inactive = str(request.query_params.get("include_inactive", "")).strip().lower() in {"1", "true", "yes"}
        memberships = TenantMembership.objects.filter(tenant=tenant)
        if include_inactive:
            # Inactive memberships are an administrative lifecycle concern, not
            # an assignable-user source. Keep the default endpoint active-only
            # for Risk/Assessment/Evidence owner selectors and require explicit
            # membership administration authority to inspect inactive accounts.
            require_whole_tenant_permission(request.user, tenant, "membership.manage")
        else:
            memberships = memberships.filter(is_active=True)
        ids = memberships.values_list("user_id", flat=True)
        users = User.objects.filter(id__in=ids).order_by("username")
        return Response(TenantUserSerializer(users, many=True, context={"tenant": tenant}).data)

    def retrieve(self, request, pk=None):
        tenant = self._tenant("membership.view")
        membership = TenantMembership.objects.filter(tenant=tenant, user_id=pk, is_active=True).first()
        if not membership:
            raise NotFound()
        return Response(TenantUserSerializer(membership.user, context={"tenant": tenant}).data)

    @transaction.atomic
    def create(self, request):
        tenant = self._tenant("membership.manage")
        serializer = TenantUserCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_audit_event(request.user, tenant, "membership.user_create", "user", None, new_data={"username": user.username, "user_id": user.pk}, request=request)
        return Response(TenantUserSerializer(user, context={"tenant": tenant}).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def partial_update(self, request, pk=None):
        tenant = self._tenant("membership.manage")
        # Administrators must be able to reactivate an existing membership. We
        # intentionally do not reactivate prior UserRoleScope rows: privilege
        # must be assigned explicitly again after an account is restored.
        membership = TenantMembership.objects.select_related("user").filter(tenant=tenant, user_id=pk).first()
        if not membership:
            raise NotFound()
        user = membership.user
        old = {"first_name": user.first_name, "last_name": user.last_name, "email": user.email, "membership_active": membership.is_active}
        changed_user_fields = []
        for key in {"first_name", "last_name", "email"}:
            if key in request.data:
                setattr(user, key, request.data[key])
                changed_user_fields.append(key)
        if changed_user_fields:
            user.save(update_fields=changed_user_fields)
        if "membership_active" in request.data:
            active = request.data["membership_active"]
            if not isinstance(active, bool):
                raise ValidationError({"membership_active": "Expected a boolean value."})
            membership.is_active = active
            membership.save(update_fields=["is_active", "updated_at"])
            if not membership.is_active:
                UserRoleScope.objects.filter(tenant=tenant, user=user, is_active=True).update(is_active=False)
        new_data = {"first_name": user.first_name, "last_name": user.last_name, "email": user.email, "membership_active": membership.is_active}
        record_audit_event(request.user, tenant, "membership.user_update", "user", None, old_data=old, new_data=new_data, metadata={"target_user_id": user.pk}, request=request)
        return Response(TenantUserSerializer(user, context={"tenant": tenant}).data)

    @action(detail=True, methods=["post"], url_path="role-assignments")
    def assign_role(self, request, pk=None):
        tenant = self._tenant("role.manage")
        payload = dict(request.data)
        payload["user"] = pk
        serializer = RoleAssignmentSerializer(data=payload, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        record_audit_event(request.user, tenant, "role.assign", "user_role_scope", assignment.id, new_data={"target_user_id": pk, "role": assignment.role.code, "scope": str(assignment.organization_unit_id or "*")}, request=request)
        return Response(RoleAssignmentSerializer(assignment, context={"tenant": tenant}).data, status=status.HTTP_201_CREATED)


class RoleAssignmentViewSet(viewsets.GenericViewSet):
    serializer_class = RoleAssignmentSerializer

    def get_queryset(self):
        tenant = resolve_tenant_for_request(self.request)
        require_whole_tenant_permission(self.request.user, tenant, "role.manage")
        self._resolved_tenant = tenant
        return UserRoleScope.objects.filter(tenant=tenant, is_active=True)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = getattr(self, "_resolved_tenant", resolve_tenant_for_request(self.request))
        return context

    def destroy(self, request, pk=None):
        assignment = self.get_object()
        assignment.is_active = False
        assignment.save(update_fields=["is_active", "updated_at"])
        record_audit_event(request.user, assignment.tenant, "role.unassign", "user_role_scope", assignment.id, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.identity.services import bootstrap_tenant_rbac, require_tenant_permission, require_whole_tenant_permission
from .models import TenantMembership
from .serializers import MembershipTenantSerializer, SecuritySettingsSerializer, TenantAdminSerializer, TenantProvisionSerializer
from .services import resolve_tenant_for_request


class MyTenantsView(generics.ListAPIView):
    serializer_class = MembershipTenantSerializer

    def get_queryset(self):
        return TenantMembership.objects.select_related("tenant").filter(
            user=self.request.user, is_active=True, tenant__status="active"
        ).order_by("tenant__name")


class CurrentTenantView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_tenant_permission(request.user, tenant, "tenant.view")
        bootstrap_tenant_rbac(tenant)
        return Response(TenantAdminSerializer(tenant).data)

    def patch(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "tenant.manage")
        old = {"name": tenant.name, "default_language": tenant.default_language, "timezone": tenant.timezone}
        serializer = TenantAdminSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        record_audit_event(request.user, tenant, "tenant.update", "tenant", tenant.id, old_data=old, new_data={"name": tenant.name, "default_language": tenant.default_language, "timezone": tenant.timezone}, request=request)
        return Response(TenantAdminSerializer(tenant).data)


class SecuritySettingsView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "security.view")
        defaults = {"require_mfa": False, "password_min_length": 12, "session_minutes": 60}
        defaults.update((tenant.settings or {}).get("security", {}))
        return Response(defaults)

    def put(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "security.manage")
        serializer = SecuritySettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old = dict((tenant.settings or {}).get("security", {}))
        settings_data = dict(tenant.settings or {})
        settings_data["security"] = serializer.validated_data
        tenant.settings = settings_data
        tenant.save(update_fields=["settings", "updated_at"])
        record_audit_event(request.user, tenant, "security.settings_update", "tenant", tenant.id, old_data=old, new_data=serializer.validated_data, request=request)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class TenantProvisionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = TenantProvisionSerializer

    def get_queryset(self):
        from .models import Tenant
        return Tenant.objects.filter(deleted_at__isnull=True).order_by("name")

    def perform_create(self, serializer):
        from django.contrib.auth import get_user_model
        admin_user_id = serializer.validated_data.pop("admin_user_id", None)
        tenant = serializer.save()
        admin_user = get_user_model().objects.filter(pk=admin_user_id).first() if admin_user_id else self.request.user
        bootstrap_tenant_rbac(tenant, admin_user=admin_user)
        record_audit_event(self.request.user, tenant, "tenant.create", "tenant", tenant.id, new_data={"name": tenant.name, "code": tenant.code}, request=self.request)

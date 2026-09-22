from rest_framework.permissions import BasePermission
from apps.tenancy.services import resolve_tenant_for_request
from .services import has_tenant_permission


class HasTenantPermission(BasePermission):
    """Views set permission_code or permission_codes_by_action."""

    def has_permission(self, request, view):
        tenant = resolve_tenant_for_request(request)
        view._resolved_tenant = tenant
        mapping = getattr(view, "permission_codes_by_action", {})
        code = mapping.get(getattr(view, "action", None)) or getattr(view, "permission_code", None)
        if not code:
            return True
        return has_tenant_permission(request.user, tenant, code)

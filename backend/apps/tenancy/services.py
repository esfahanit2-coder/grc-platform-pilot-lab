from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Tenant, TenantMembership

def resolve_tenant_for_request(request) -> Tenant:
    tenant_id = getattr(request, "tenant_id", None)
    if tenant_id is None:
        raise ValidationError({"tenant": "X-Tenant-ID header is required for this resource."})
    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(tenant_id=tenant_id, user=request.user, is_active=True, tenant__status="active")
        .first()
    )
    if not membership:
        raise PermissionDenied("You are not an active member of the selected tenant.")
    return membership.tenant

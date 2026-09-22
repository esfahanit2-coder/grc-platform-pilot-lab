from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.frameworks.services import requirement_visible
from .models import Control, ControlRequirement


def visible_controls(tenant):
    return Control.objects.filter(deleted_at__isnull=True).filter(Q(tenant=tenant) | Q(tenant__isnull=True, status=Control.Status.ACTIVE))


def control_visible(control, tenant):
    return control.deleted_at is None and (control.tenant_id == tenant.id or (control.tenant_id is None and control.status == Control.Status.ACTIVE))


def require_local_control(control, tenant):
    if control.tenant_id != tenant.id:
        raise PermissionDenied("Global/reference controls are read-only for tenant users. Duplicate them before editing.")


def validate_control_requirement(control, requirement, tenant):
    if not control_visible(control, tenant):
        raise PermissionDenied("Control is not visible to this tenant.")
    if not requirement_visible(requirement, tenant):
        raise PermissionDenied("Requirement is not visible to this tenant.")


def coverage_by_framework(control, tenant):
    qs = ControlRequirement.objects.filter(control=control, deleted_at__isnull=True).filter(Q(tenant=tenant) | Q(tenant__isnull=True)).select_related("requirement__framework_version__framework")
    result = {}
    for row in qs:
        fw = row.requirement.framework_version.framework
        result.setdefault(fw.code, {"framework": fw.name, "requirements": 0, "coverage": 0.0})
        result[fw.code]["requirements"] += 1
        result[fw.code]["coverage"] += float(row.coverage)
    for item in result.values():
        if item["requirements"]:
            item["coverage"] = round(item["coverage"] / item["requirements"], 2)
    return result

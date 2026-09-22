import base64
import hashlib
from datetime import timedelta

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership
from .models import MFADevice, Permission, Role, RolePermission, UserRoleScope


PERMISSION_CATALOG = [
    ("tenant.view", "tenant", "View tenant settings"),
    ("tenant.manage", "tenant", "Manage tenant settings"),
    ("membership.view", "identity", "View tenant users"),
    ("membership.manage", "identity", "Manage tenant users"),
    ("role.view", "identity", "View roles and permissions"),
    ("role.manage", "identity", "Manage roles and assignments"),
    ("organization.view", "organization", "View organization structure"),
    ("organization.manage", "organization", "Manage organization structure"),
    ("audit.view", "audit", "View audit trail"),
    ("security.view", "security", "View security configuration"),
    ("security.manage", "security", "Manage security configuration"),
    ("framework.view", "framework", "View framework library and requirements"),
    ("framework.manage", "framework", "Create and manage tenant frameworks"),
    ("framework.import", "framework", "Import framework content packs"),
    ("framework.mapping.view", "framework", "View requirement crosswalk mappings"),
    ("framework.mapping.manage", "framework", "Create and approve requirement crosswalk mappings"),
    ("control.view", "control", "View common control library"),
    ("control.manage", "control", "Manage tenant control definitions and mappings"),
    ("control.implementation.view", "control", "View control implementations in assigned scope"),
    ("control.implementation.manage", "control", "Manage control implementations in assigned scope"),
    ("asset.view", "asset", "View asset register in assigned scope"),
    ("asset.manage", "asset", "Manage assets in assigned scope"),
    ("risk.view", "risk", "View risks and methodologies in assigned scope"),
    ("risk.manage", "risk", "Create and manage risks in assigned scope"),
    ("risk.evaluate", "risk", "Evaluate risk using approved methodologies"),
    ("risk.treatment.manage", "risk", "Manage and approve risk treatments"),
    ("action.view", "action", "View GRC actions in assigned scope"),
    ("action.manage", "action", "Manage GRC actions in assigned scope"),
    ("assessment.view", "assessment", "View assessments in assigned scope"),
    ("assessment.manage", "assessment", "Create and manage assessments in assigned scope"),
    ("assessment.perform", "assessment", "Perform requirement assessments in assigned scope"),
    ("assessment.review", "assessment", "Review and complete assessments in assigned scope"),
    ("evidence.view", "evidence", "View reusable evidence in assigned scope"),
    ("evidence.manage", "evidence", "Create, link and manage evidence in assigned scope"),
    ("finding.view", "finding", "View findings in assigned scope"),
    ("finding.manage", "finding", "Create and remediate findings in assigned scope"),
    ("finding.close", "finding", "Verify and close findings in assigned scope"),
    ("internal_audit.view", "internal_audit", "View audit plans, engagements and workpapers"),
    ("internal_audit.manage", "internal_audit", "Manage audit plans and engagements"),
    ("internal_audit.perform", "internal_audit", "Perform audit workpapers"),
    ("internal_audit.review", "internal_audit", "Review audits and workpapers"),
    ("control.test.view", "control", "View control tests and results"),
    ("control.test.manage", "control", "Manage control test definitions"),
    ("control.test.execute", "control", "Execute control tests"),
    ("document.view", "document", "View controlled documents"),
    ("document.manage", "document", "Create and manage controlled documents"),
    ("document.approve", "document", "Approve controlled documents"),
    ("report.view", "reporting", "View management dashboards and reports"),
    ("report.generate", "reporting", "Generate formal GRC reports"),
    ("ai.use", "ai", "Use approved AI assistants"),
    ("ai.configure", "ai", "Configure tenant AI providers and policies"),
    ("ai.audit", "ai", "Audit tenant AI interactions and suggestions"),
    ("ai.knowledge.view", "ai", "View authorized AI knowledge chunks"),
    ("ai.knowledge.manage", "ai", "Manage tenant AI knowledge sources"),
    ("workflow.view", "workflow", "View workflow definitions and instances"),
    ("workflow.manage", "workflow", "Configure tenant workflows"),
    ("workflow.start", "workflow", "Start workflows for objects in assigned scope"),
    ("workflow.transition", "workflow", "Transition workflows in assigned scope"),
    ("connector.view", "connector", "View connector configurations and sync history"),
    ("connector.manage", "connector", "Manage connector configurations"),
    ("connector.run", "connector", "Run approved read-only connector collections"),
]

SYSTEM_ROLES = {
    "tenant_admin": {
        "name": "Tenant Administrator",
        "permissions": [code for code, _, _ in PERMISSION_CATALOG],
    },
    "grc_manager": {
        "name": "GRC Manager",
        "permissions": [
            "tenant.view", "membership.view", "role.view",
            "organization.view", "organization.manage", "audit.view", "security.view",
            "framework.view", "framework.manage", "framework.import",
            "framework.mapping.view", "framework.mapping.manage",
            "control.view", "control.manage", "control.implementation.view", "control.implementation.manage",
            "asset.view", "asset.manage",
            "risk.view", "risk.manage", "risk.evaluate", "risk.treatment.manage",
            "action.view", "action.manage",
            "assessment.view", "assessment.manage", "assessment.perform", "assessment.review",
            "evidence.view", "evidence.manage", "finding.view", "finding.manage", "finding.close",
            "internal_audit.view",
            "internal_audit.manage",
            "internal_audit.perform",
            "internal_audit.review",
            "control.test.view",
            "control.test.manage",
            "control.test.execute",
            "document.view",
            "document.manage",
            "document.approve",
            "report.view",
            "report.generate",
            "ai.use", "ai.configure", "ai.audit", "ai.knowledge.view", "ai.knowledge.manage",
            "workflow.view", "workflow.manage", "workflow.start", "workflow.transition",
            "connector.view", "connector.manage", "connector.run",
        ],
    },
    "compliance_manager": {
        "name": "Compliance Manager",
        "permissions": [
            "tenant.view", "organization.view", "framework.view", "framework.mapping.view",
            "control.view", "control.implementation.view", "risk.view", "asset.view",
            "assessment.view", "assessment.manage", "assessment.perform", "assessment.review",
            "evidence.view", "evidence.manage", "finding.view", "finding.manage", "finding.close",
            "action.view", "action.manage",
            "internal_audit.view",
            "internal_audit.perform",
            "control.test.view",
            "document.view",
            "document.manage",
            "document.approve",
            "report.view",
            "report.generate",
            "ai.use", "ai.knowledge.view",
            "workflow.view", "workflow.start", "workflow.transition", "connector.view", "connector.run",
        ],
    },
    "risk_manager": {
        "name": "Risk Manager",
        "permissions": [
            "tenant.view", "organization.view", "framework.view", "framework.mapping.view",
            "control.view", "control.implementation.view", "control.implementation.manage",
            "asset.view", "asset.manage", "risk.view", "risk.manage", "risk.evaluate", "risk.treatment.manage",
            "action.view", "action.manage",
            "assessment.view", "assessment.perform", "evidence.view", "evidence.manage", "finding.view", "finding.manage",
            "internal_audit.view",
            "control.test.view",
            "control.test.execute",
            "document.view",
            "report.view",
            "ai.use", "ai.knowledge.view",
            "workflow.view", "workflow.start", "workflow.transition", "connector.view", "connector.run",
        ],
    },
    "control_owner": {
        "name": "Control Owner",
        "permissions": [
            "tenant.view", "organization.view", "framework.view", "control.view",
            "control.implementation.view", "control.implementation.manage", "asset.view", "risk.view", "action.view", "action.manage",
            "assessment.view", "assessment.perform", "evidence.view", "evidence.manage", "finding.view",
            "control.test.view",
            "control.test.manage",
            "control.test.execute",
            "document.view",
            "report.view",
            "ai.use", "ai.knowledge.view",
            "workflow.view", "workflow.start", "workflow.transition", "connector.view", "connector.run",
        ],
    },
    "auditor": {
        "name": "Auditor",
        "permissions": [
            "tenant.view", "organization.view", "audit.view", "framework.view", "framework.mapping.view",
            "control.view", "control.implementation.view", "asset.view", "risk.view", "action.view",
            "assessment.view", "assessment.perform", "assessment.review", "evidence.view", "finding.view", "finding.manage", "finding.close",
            "internal_audit.view",
            "internal_audit.manage",
            "internal_audit.perform",
            "internal_audit.review",
            "control.test.view",
            "control.test.execute",
            "document.view",
            "report.view",
            "report.generate",
            "ai.use", "ai.audit", "ai.knowledge.view",
            "workflow.view", "workflow.start", "workflow.transition", "connector.view", "connector.run",
        ],
    },
    "viewer": {
        "name": "Viewer",
        "permissions": [
            "tenant.view", "organization.view", "framework.view", "framework.mapping.view",
            "control.view", "control.implementation.view", "asset.view", "risk.view", "action.view",
            "assessment.view", "evidence.view", "finding.view",
            "internal_audit.view",
            "control.test.view",
            "document.view",
            "report.view",
            "ai.knowledge.view", "workflow.view", "connector.view",
        ],
    },
}


def ensure_permission_catalog():
    result = {}
    for code, module, description in PERMISSION_CATALOG:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"module": module, "name": code.replace(".", " ").title(), "description": description},
        )
        if permission.module != module or permission.description != description:
            permission.module = module
            permission.description = description
            permission.save(update_fields=["module", "description", "updated_at"])
        result[code] = permission
    return result


def bootstrap_tenant_rbac(tenant: Tenant, admin_user=None):
    permissions = ensure_permission_catalog()
    roles = {}
    for code, config in SYSTEM_ROLES.items():
        role, _ = Role.objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": config["name"], "is_system": True},
        )
        if not role.is_system:
            role.is_system = True
            role.save(update_fields=["is_system", "updated_at"])
        RolePermission.objects.filter(role=role).exclude(permission__code__in=config["permissions"]).delete()
        for permission_code in config["permissions"]:
            RolePermission.objects.get_or_create(role=role, permission=permissions[permission_code])
        roles[code] = role

    if admin_user is not None:
        TenantMembership.objects.get_or_create(tenant=tenant, user=admin_user, defaults={"role_code": "admin"})
        UserRoleScope.objects.get_or_create(
            tenant=tenant,
            user=admin_user,
            role=roles["tenant_admin"],
            organization_unit=None,
            defaults={"is_active": True},
        )
    return roles


def _assignment_queryset(user, tenant, permission_code):
    now = timezone.now()
    return UserRoleScope.objects.select_related("role", "organization_unit").filter(
        user=user,
        tenant=tenant,
        is_active=True,
        role__is_active=True,
        role__role_permissions__permission__code=permission_code,
        role__role_permissions__permission__is_active=True,
    ).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now)).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now)).distinct()


def has_tenant_permission(user, tenant, permission_code, organization_unit=None):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if not TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
        return False

    assignments = list(_assignment_queryset(user, tenant, permission_code))
    if not assignments:
        # Compatibility path for Sprint 0 administrators. Remove after all tenants are migrated.
        return TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True, role_code="admin").exists()
    if organization_unit is None:
        return any(item.organization_unit_id is None for item in assignments) or bool(assignments)
    for item in assignments:
        if item.organization_unit_id is None:
            return True
        node = organization_unit
        visited = set()
        while node is not None and node.id not in visited:
            if node.id == item.organization_unit_id:
                return True
            visited.add(node.id)
            node = node.parent
    return False


def require_tenant_permission(user, tenant, permission_code, organization_unit=None):
    if not has_tenant_permission(user, tenant, permission_code, organization_unit):
        raise PermissionDenied(f"Missing permission: {permission_code}")



def has_whole_tenant_permission(user, tenant, permission_code):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if not TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).exists():
        return False
    if _assignment_queryset(user, tenant, permission_code).filter(organization_unit__isnull=True).exists():
        return True
    return TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True, role_code="admin").exists()


def require_whole_tenant_permission(user, tenant, permission_code):
    if not has_whole_tenant_permission(user, tenant, permission_code):
        raise PermissionDenied(f"Missing whole-tenant permission: {permission_code}")

def accessible_organization_unit_ids(user, tenant, permission_code):
    if user.is_superuser:
        return list(OrganizationUnit.objects.for_tenant(tenant).filter(deleted_at__isnull=True).values_list("id", flat=True))
    assignments = list(_assignment_queryset(user, tenant, permission_code))
    if any(item.organization_unit_id is None for item in assignments):
        return list(OrganizationUnit.objects.for_tenant(tenant).filter(deleted_at__isnull=True).values_list("id", flat=True))
    roots = {item.organization_unit_id for item in assignments if item.organization_unit_id}
    if not roots:
        return []
    rows = list(OrganizationUnit.objects.for_tenant(tenant).filter(deleted_at__isnull=True).values("id", "parent_id"))
    children = {}
    for row in rows:
        children.setdefault(row["parent_id"], []).append(row["id"])
    result = set(roots)
    stack = list(roots)
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            if child not in result:
                result.add(child)
                stack.append(child)
    return list(result)


def _fernet():
    explicit = getattr(settings, "MFA_ENCRYPTION_KEY", "")
    if explicit:
        key = explicit.encode("utf-8")
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_mfa_secret(secret):
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_mfa_secret(value):
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("MFA secret cannot be decrypted. Check MFA_ENCRYPTION_KEY.") from exc


def create_pending_mfa_device(user, name="Authenticator"):
    MFADevice.objects.filter(user=user, is_active=False).delete()
    secret = pyotp.random_base32()
    device = MFADevice.objects.create(user=user, name=name, encrypted_secret=encrypt_mfa_secret(secret), is_active=False)
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.get_username(), issuer_name=getattr(settings, "MFA_ISSUER", "GRC Platform"))
    return device, secret, uri


def verify_mfa_device(device, otp):
    secret = decrypt_mfa_secret(device.encrypted_secret)
    valid = pyotp.TOTP(secret).verify(str(otp or "").strip(), valid_window=1)
    if valid:
        device.last_used_at = timezone.now()
        device.save(update_fields=["last_used_at", "updated_at"])
    return valid


def tenant_requires_mfa(user):
    memberships = TenantMembership.objects.select_related("tenant").filter(user=user, is_active=True, tenant__status="active")
    for membership in memberships:
        security = (membership.tenant.settings or {}).get("security", {})
        if security.get("require_mfa") is True:
            return True
    return False

import hashlib
import json
from copy import deepcopy

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Framework, FrameworkVersion, Requirement, RequirementMapping, RequirementTranslation


def visible_frameworks(tenant):
    return Framework.objects.filter(deleted_at__isnull=True).filter(
        Q(tenant=tenant) | Q(tenant__isnull=True, status=Framework.Status.ACTIVE)
    )


def framework_is_visible(framework, tenant):
    return framework.deleted_at is None and (
        framework.tenant_id == tenant.id or (framework.tenant_id is None and framework.status == Framework.Status.ACTIVE)
    )


def require_local_framework(framework, tenant):
    if framework.tenant_id != tenant.id:
        raise PermissionDenied("Global/reference frameworks are read-only for tenant users. Duplicate them before editing.")


def require_editable_version(version, tenant):
    require_local_framework(version.framework, tenant)
    if version.is_locked:
        raise ValidationError({"framework_version": "This framework version is locked and immutable."})


def canonical_version_payload(version):
    requirements = []
    qs = version.requirements.filter(deleted_at__isnull=True).select_related("parent").prefetch_related("translations").order_by("sort_order", "code", "id")
    for req in qs:
        requirements.append({
            "code": req.code,
            "parent": req.parent.code if req.parent_id else None,
            "title": req.title,
            "body": req.body,
            "guidance": req.guidance,
            "assessable": req.assessable,
            "mandatory": req.mandatory,
            "weight": str(req.weight),
            "sort_order": req.sort_order,
            "metadata": req.metadata,
            "translations": [
                {"language": tr.language, "title": tr.title, "body": tr.body, "guidance": tr.guidance}
                for tr in sorted(req.translations.all(), key=lambda x: x.language)
            ],
        })
    return {
        "framework": version.framework.code,
        "version": version.version_code,
        "requirements": requirements,
    }


def calculate_version_checksum(version):
    raw = json.dumps(canonical_version_payload(version), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lock_framework_version(version, tenant):
    require_local_framework(version.framework, tenant)
    if version.is_locked:
        return version
    version.checksum = calculate_version_checksum(version)
    version.is_locked = True
    if version.status == FrameworkVersion.Status.DRAFT:
        version.status = FrameworkVersion.Status.ACTIVE
    version.save(update_fields=["checksum", "is_locked", "status", "updated_at"])
    return version


@transaction.atomic
def duplicate_framework(source, tenant, user, *, code, name=None, version_id=None):
    if Framework.objects.filter(tenant=tenant, code=code, deleted_at__isnull=True).exists():
        raise ValidationError({"code": "A framework with this code already exists in the tenant."})
    clone = Framework.objects.create(
        tenant=tenant,
        code=code,
        name=name or source.name,
        publisher=source.publisher,
        framework_type=source.framework_type,
        content_source=Framework.ContentSource.CUSTOMER,
        license_type=source.license_type,
        license_metadata=deepcopy(source.license_metadata),
        description=source.description,
        status=Framework.Status.DRAFT,
        created_by=user,
    )
    versions = source.versions.filter(deleted_at__isnull=True)
    if source.is_global:
        versions = versions.filter(status=FrameworkVersion.Status.ACTIVE)
    if version_id:
        versions = versions.filter(id=version_id)
    for source_version in versions.order_by("created_at"):
        new_version = FrameworkVersion.objects.create(
            framework=clone,
            version_code=source_version.version_code,
            title=source_version.title,
            publication_date=source_version.publication_date,
            effective_date=source_version.effective_date,
            retirement_date=source_version.retirement_date,
            status=FrameworkVersion.Status.DRAFT,
            is_locked=False,
            metadata=deepcopy(source_version.metadata),
            created_by=user,
        )
        req_map = {}
        source_reqs = list(source_version.requirements.prefetch_related("translations").order_by("sort_order", "code"))
        for req in source_reqs:
            new_req = Requirement.objects.create(
                framework_version=new_version,
                code=req.code,
                title=req.title,
                body=req.body,
                guidance=req.guidance,
                assessable=req.assessable,
                mandatory=req.mandatory,
                weight=req.weight,
                sort_order=req.sort_order,
                metadata=deepcopy(req.metadata),
            )
            req_map[req.id] = new_req
            for tr in req.translations.all():
                RequirementTranslation.objects.create(
                    requirement=new_req,
                    language=tr.language,
                    title=tr.title,
                    body=tr.body,
                    guidance=tr.guidance,
                )
        for req in source_reqs:
            if req.parent_id:
                new_req = req_map[req.id]
                new_req.parent = req_map[req.parent_id]
                new_req.save(update_fields=["parent", "updated_at"])
    return clone


def requirement_visible(requirement, tenant):
    framework = requirement.framework_version.framework
    if not framework_is_visible(framework, tenant):
        return False
    if framework.is_global and requirement.framework_version.status != FrameworkVersion.Status.ACTIVE:
        return False
    return requirement.deleted_at is None and requirement.framework_version.deleted_at is None


def validate_mapping_access(source_requirement, target_requirement, tenant):
    if not requirement_visible(source_requirement, tenant) or not requirement_visible(target_requirement, tenant):
        raise PermissionDenied("Both requirements must belong to frameworks visible to the selected tenant.")

import csv
import hashlib
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.assets.models import Asset
from apps.assets.serializers import AssetSerializer
from apps.controls.models import Control, ControlCategory
from apps.controls.serializers import ControlSerializer
from apps.identity.models import UserRoleScope
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.organizations.models import OrganizationUnit
from apps.organizations.serializers import OrganizationUnitSerializer
from apps.risks.models import Risk
from apps.risks.serializers import RiskSerializer
from apps.tenancy.models import TenantMembership

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
TOKEN_SALT = "grc-data-exchange-v1"
TOKEN_MAX_AGE = 30 * 60

DATASETS = {
    "organization": {
        "label": "ساختار سازمانی",
        "headers": ["code", "name", "unit_type", "parent_code", "name_en", "manager_username", "status"],
        "view_permission": "organization.view",
        "manage_permission": "organization.manage",
    },
    "users": {
        "label": "کاربران Tenant",
        "headers": ["username", "first_name", "last_name", "email", "membership_active"],
        "view_permission": "membership.view",
        "manage_permission": "membership.manage",
    },
    "assets": {
        "label": "دارایی‌ها",
        "headers": [
            "code", "title", "asset_type", "organization_code", "owner_username",
            "custodian_username", "description", "confidentiality", "integrity",
            "availability", "criticality", "status",
        ],
        "view_permission": "asset.view",
        "manage_permission": "asset.manage",
    },
    "risks": {
        "label": "ریسک‌ها",
        "headers": [
            "code", "title", "organization_code", "asset_code", "owner_username",
            "status", "review_date", "scenario", "cause", "consequence",
        ],
        "view_permission": "risk.view",
        "manage_permission": "risk.manage",
    },
    "controls": {
        "label": "کنترل‌های محلی Tenant",
        "headers": [
            "code", "title", "description", "objective", "control_type", "nature",
            "frequency", "automation_level", "status", "category_code",
        ],
        "view_permission": "control.view",
        "manage_permission": "control.manage",
    },
}


class ImportedUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    membership_active = serializers.BooleanField(default=True)


def dataset_config(dataset):
    config = DATASETS.get(str(dataset or "").strip().lower())
    if not config:
        raise ValidationError({"dataset": "Unsupported dataset."})
    return config


def _safe_cell(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _file_format(filename):
    name = str(filename or "").lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".xlsx"):
        return "xlsx"
    raise ValidationError({"file": "Only .csv and .xlsx files are supported."})


def read_upload(upload, dataset):
    if upload is None:
        raise ValidationError({"file": "File is required."})
    raw = upload.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "File exceeds the 5 MB limit."})
    fmt = _file_format(upload.name)
    expected = DATASETS[dataset]["headers"]

    if fmt == "csv":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError({"file": "CSV must be UTF-8."}) from exc
        reader = csv.DictReader(StringIO(text))
        actual = [str(x or "").strip() for x in (reader.fieldnames or [])]
        raw_rows = list(reader)
    else:
        try:
            wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            values = ws.iter_rows(values_only=True)
            actual = [str(x or "").strip() for x in next(values, [])]
            raw_rows = [dict(zip(actual, row)) for row in values]
        except Exception as exc:
            raise ValidationError({"file": "Invalid XLSX workbook."}) from exc

    if len(actual) != len(set(actual)):
        raise ValidationError({"file": "Duplicate column names are not allowed."})
    missing = [h for h in expected if h not in actual]
    unknown = [h for h in actual if h not in expected]
    if missing or unknown:
        raise ValidationError({"file": {"missing_columns": missing, "unknown_columns": unknown}})
    if len(raw_rows) > MAX_ROWS:
        raise ValidationError({"file": f"Maximum {MAX_ROWS} data rows are allowed."})

    rows = []
    for row in raw_rows:
        normalized = {h: "" if row.get(h) is None else str(row.get(h)).strip() for h in expected}
        if any(value != "" for value in normalized.values()):
            rows.append(normalized)
    return raw, fmt, rows


def render_table(headers, rows, fmt):
    if fmt not in {"csv", "xlsx"}:
        raise ValidationError({"format": "Only csv and xlsx are supported."})
    if fmt == "csv":
        out = StringIO()
        writer = csv.writer(out)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_safe_cell(row.get(h, "")) for h in headers])
        return out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"

    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(headers)
    for row in rows:
        ws.append([_safe_cell(row.get(h, "")) for h in headers])
    out = BytesIO()
    wb.save(out)
    return out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _member_user(tenant, username, required=True):
    username = str(username or "").strip()
    if not username:
        if required:
            raise ValidationError({"user": "Username is required."})
        return None
    membership = TenantMembership.objects.select_related("user").filter(
        tenant=tenant, user__username__iexact=username, is_active=True
    ).first()
    if not membership:
        raise ValidationError({"user": f"Active tenant user not found: {username}"})
    return membership.user


def _unit_by_code(tenant, code, required=True):
    code = str(code or "").strip()
    if not code:
        if required:
            raise ValidationError({"organization_code": "Organization code is required."})
        return None
    unit = OrganizationUnit.objects.for_tenant(tenant).filter(code=code, deleted_at__isnull=True).first()
    if not unit:
        raise ValidationError({"organization_code": f"Organization unit not found: {code}"})
    return unit


def _asset_by_code(tenant, code, required=False):
    code = str(code or "").strip()
    if not code:
        if required:
            raise ValidationError({"asset_code": "Asset code is required."})
        return None
    asset = Asset.objects.filter(tenant=tenant, code=code, deleted_at__isnull=True).first()
    if not asset:
        raise ValidationError({"asset_code": f"Asset not found: {code}"})
    return asset


def _category_by_code(tenant, code):
    code = str(code or "").strip()
    if not code:
        return None
    category = ControlCategory.objects.filter(
        code=code, deleted_at__isnull=True, tenant=tenant
    ).first()
    if not category:
        category = ControlCategory.objects.filter(
            code=code, deleted_at__isnull=True, tenant__isnull=True
        ).first()
    if not category:
        raise ValidationError({"category_code": f"Control category not found: {code}"})
    return category


def _error_payload(exc):
    if isinstance(exc, ValidationError):
        return exc.detail
    if isinstance(exc, PermissionDenied):
        return {"permission": str(exc.detail)}
    return {"detail": str(exc)}


def _row_result(number, key, action, errors=None):
    return {
        "row": number,
        "key": key,
        "action": action,
        "errors": errors or {},
    }


def _validate_organization_rows(rows, request, tenant, apply=False):
    codes = [row["code"] for row in rows]
    if any(not code for code in codes):
        return [_row_result(i + 2, row["code"], "error", {"code": "Code is required."}) for i, row in enumerate(rows) if not row["code"]], []
    duplicates = {code for code in codes if codes.count(code) > 1}
    known = {
        unit.code: unit
        for unit in OrganizationUnit.objects.for_tenant(tenant).filter(deleted_at__isnull=True)
    }
    row_map = {row["code"]: row for row in rows}
    results = []
    if duplicates:
        for i, row in enumerate(rows):
            if row["code"] in duplicates:
                results.append(_row_result(i + 2, row["code"], "error", {"code": "Duplicate code in file."}))
        return results, []

    for i, row in enumerate(rows):
        parent_code = row["parent_code"]
        if parent_code and parent_code not in known and parent_code not in row_map:
            results.append(_row_result(i + 2, row["code"], "error", {"parent_code": "Parent code not found."}))

    visiting, visited = set(), set()
    def visit(code):
        if code in visited:
            return
        if code in visiting:
            raise ValidationError({"parent_code": f"Hierarchy cycle detected at {code}."})
        visiting.add(code)
        parent = row_map.get(code, {}).get("parent_code")
        if parent in row_map:
            visit(parent)
        visiting.remove(code)
        visited.add(code)
    try:
        for code in row_map:
            visit(code)
    except ValidationError as exc:
        return [_row_result(2, "", "error", exc.detail)], []

    if results:
        return results, []

    order = []
    visited.clear()
    def append_order(code):
        if code in visited:
            return
        parent = row_map[code]["parent_code"]
        if parent in row_map:
            append_order(parent)
        visited.add(code)
        order.append(code)
    for code in row_map:
        append_order(code)

    for code in order:
        row = row_map[code]
        number = rows.index(row) + 2
        existing = known.get(code)
        try:
            parent = known.get(row["parent_code"]) if row["parent_code"] else None
            manager = _member_user(tenant, row["manager_username"], required=False)
            if existing:
                require_tenant_permission(request.user, tenant, "organization.manage", existing)
                if row["parent_code"]:
                    if parent is None and apply:
                        parent = OrganizationUnit.objects.for_tenant(tenant).filter(code=row["parent_code"], deleted_at__isnull=True).first()
                    if parent:
                        require_tenant_permission(request.user, tenant, "organization.manage", parent)
                else:
                    require_whole_tenant_permission(request.user, tenant, "organization.manage")
            elif parent:
                require_tenant_permission(request.user, tenant, "organization.manage", parent)
            elif row["parent_code"] and row["parent_code"] in row_map:
                # File-local parent is authorized when it is itself authorized earlier in topological order.
                pass
            else:
                require_whole_tenant_permission(request.user, tenant, "organization.manage")

            payload = {
                "parent": str(parent.id) if parent else None,
                "unit_type": row["unit_type"],
                "code": row["code"],
                "name": row["name"],
                "name_en": row["name_en"],
                "manager": manager.pk if manager else None,
                "status": row["status"] or "active",
            }
            serializer = OrganizationUnitSerializer(
                existing, data=payload, context={"tenant": tenant}
            )
            serializer.is_valid(raise_exception=True)
            if apply:
                obj = serializer.save(tenant=tenant) if existing is None else serializer.save()
                known[code] = obj
            results.append(_row_result(number, code, "update" if existing else "create"))
        except Exception as exc:
            results.append(_row_result(number, code, "error", _error_payload(exc)))
    return results, order


def _validate_user_rows(rows, request, tenant, apply=False):
    require_whole_tenant_permission(request.user, tenant, "membership.manage")
    User = get_user_model()
    results = []
    seen = set()
    for i, row in enumerate(rows):
        key = row["username"]
        normalized_key = key.casefold()
        try:
            if normalized_key in seen:
                raise ValidationError({"username": "Duplicate username in file."})
            seen.add(normalized_key)
            ser = ImportedUserSerializer(data=row)
            ser.is_valid(raise_exception=True)
            data = ser.validated_data
            existing = User.objects.filter(username__iexact=data["username"]).first()
            membership = TenantMembership.objects.filter(tenant=tenant, user=existing).first() if existing else None
            if existing and membership is None:
                raise ValidationError({"username": "Username already belongs to an identity outside this tenant; automatic attachment is not allowed."})
            was_existing = membership is not None
            if apply:
                if existing is None:
                    existing = User(
                        username=data["username"],
                        first_name=data.get("first_name", ""),
                        last_name=data.get("last_name", ""),
                        email=data.get("email", ""),
                    )
                    existing.set_unusable_password()
                    existing.save()
                    membership = TenantMembership.objects.create(
                        tenant=tenant, user=existing, role_code="member",
                        is_active=data["membership_active"],
                    )
                else:
                    existing.first_name = data.get("first_name", "")
                    existing.last_name = data.get("last_name", "")
                    existing.email = data.get("email", "")
                    existing.save(update_fields=["first_name", "last_name", "email"])
                    membership.is_active = data["membership_active"]
                    membership.save(update_fields=["is_active", "updated_at"])
                    if not membership.is_active:
                        UserRoleScope.objects.filter(tenant=tenant, user=existing, is_active=True).update(is_active=False)
            results.append(_row_result(i + 2, key, "update" if was_existing else "create"))
        except Exception as exc:
            results.append(_row_result(i + 2, key, "error", _error_payload(exc)))
    return results, []


def _validate_asset_rows(rows, request, tenant, apply=False):
    results = []
    seen = set()
    for i, row in enumerate(rows):
        key = row["code"]
        try:
            if not key:
                raise ValidationError({"code": "Code is required."})
            if key in seen:
                raise ValidationError({"code": "Duplicate code in file."})
            seen.add(key)
            existing = Asset.objects.filter(tenant=tenant, code=key).first()
            if existing and existing.deleted_at:
                raise ValidationError({"code": "Archived asset must be restored explicitly before import."})
            unit = _unit_by_code(tenant, row["organization_code"])
            owner = _member_user(tenant, row["owner_username"])
            custodian = _member_user(tenant, row["custodian_username"], required=False)
            if existing:
                require_tenant_permission(request.user, tenant, "asset.manage", existing.organization_unit)
            require_tenant_permission(request.user, tenant, "asset.manage", unit)
            payload = {
                "organization_unit": str(unit.id),
                "asset_type": row["asset_type"],
                "code": key,
                "title": row["title"],
                "description": row["description"],
                "owner": owner.pk,
                "custodian": custodian.pk if custodian else None,
                "confidentiality": row["confidentiality"] or 3,
                "integrity": row["integrity"] or 3,
                "availability": row["availability"] or 3,
                "criticality": row["criticality"] or 3,
                "status": row["status"] or "active",
            }
            ser = AssetSerializer(existing, data=payload, context={"tenant": tenant})
            ser.is_valid(raise_exception=True)
            if apply:
                ser.save(tenant=tenant) if existing is None else ser.save()
            results.append(_row_result(i + 2, key, "update" if existing else "create"))
        except Exception as exc:
            results.append(_row_result(i + 2, key, "error", _error_payload(exc)))
    return results, []


def _validate_risk_rows(rows, request, tenant, apply=False):
    results = []
    seen = set()
    for i, row in enumerate(rows):
        key = row["code"]
        try:
            if not key:
                raise ValidationError({"code": "Code is required."})
            if key in seen:
                raise ValidationError({"code": "Duplicate code in file."})
            seen.add(key)
            existing = Risk.objects.filter(tenant=tenant, code=key).first()
            if existing and existing.deleted_at:
                raise ValidationError({"code": "Archived risk must be restored explicitly before import."})
            unit = _unit_by_code(tenant, row["organization_code"], required=False)
            asset = _asset_by_code(tenant, row["asset_code"], required=False)
            owner = _member_user(tenant, row["owner_username"])
            if existing:
                if existing.organization_unit:
                    require_tenant_permission(request.user, tenant, "risk.manage", existing.organization_unit)
                else:
                    require_whole_tenant_permission(request.user, tenant, "risk.manage")
            if unit:
                require_tenant_permission(request.user, tenant, "risk.manage", unit)
            else:
                require_whole_tenant_permission(request.user, tenant, "risk.manage")
            payload = {
                "organization_unit": str(unit.id) if unit else None,
                "asset": str(asset.id) if asset else None,
                "code": key,
                "title": row["title"],
                "scenario": row["scenario"],
                "cause": row["cause"],
                "consequence": row["consequence"],
                "owner": owner.pk,
                "status": row["status"] or "draft",
                "review_date": row["review_date"] or None,
            }
            ser = RiskSerializer(existing, data=payload, context={"tenant": tenant})
            ser.is_valid(raise_exception=True)
            if apply:
                ser.save(tenant=tenant) if existing is None else ser.save()
            results.append(_row_result(i + 2, key, "update" if existing else "create"))
        except Exception as exc:
            results.append(_row_result(i + 2, key, "error", _error_payload(exc)))
    return results, []


def _validate_control_rows(rows, request, tenant, apply=False):
    require_whole_tenant_permission(request.user, tenant, "control.manage")
    results = []
    seen = set()
    for i, row in enumerate(rows):
        key = row["code"]
        try:
            if not key:
                raise ValidationError({"code": "Code is required."})
            if key in seen:
                raise ValidationError({"code": "Duplicate code in file."})
            seen.add(key)
            existing = Control.objects.filter(tenant=tenant, code=key).first()
            if existing and existing.deleted_at:
                raise ValidationError({"code": "Archived control must be restored explicitly before import."})
            category = _category_by_code(tenant, row["category_code"])
            payload = {
                "code": key,
                "title": row["title"],
                "description": row["description"],
                "objective": row["objective"],
                "category": str(category.id) if category else None,
                "control_type": row["control_type"] or "administrative",
                "nature": row["nature"] or "preventive",
                "frequency": row["frequency"],
                "automation_level": row["automation_level"] or "manual",
                "status": row["status"] or "draft",
            }
            ser = ControlSerializer(existing, data=payload, context={"tenant": tenant})
            ser.is_valid(raise_exception=True)
            if apply:
                ser.save(tenant=tenant, created_by=request.user) if existing is None else ser.save()
            results.append(_row_result(i + 2, key, "update" if existing else "create"))
        except Exception as exc:
            results.append(_row_result(i + 2, key, "error", _error_payload(exc)))
    return results, []


VALIDATORS = {
    "organization": _validate_organization_rows,
    "users": _validate_user_rows,
    "assets": _validate_asset_rows,
    "risks": _validate_risk_rows,
    "controls": _validate_control_rows,
}


def plan_import(dataset, rows, request, tenant, apply=False):
    results, _ = VALIDATORS[dataset](rows, request, tenant, apply=apply)
    errors = [row for row in results if row["errors"]]
    return {
        "dataset": dataset,
        "row_count": len(rows),
        "create_count": sum(1 for row in results if row["action"] == "create" and not row["errors"]),
        "update_count": sum(1 for row in results if row["action"] == "update" and not row["errors"]),
        "error_count": len(errors),
        "results": results,
    }


def make_validation_token(raw, dataset, tenant, user, fmt, row_count):
    return signing.dumps(
        {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "dataset": dataset,
            "tenant": str(tenant.id),
            "user": str(user.pk),
            "format": fmt,
            "rows": row_count,
        },
        salt=TOKEN_SALT,
        compress=True,
    )


def verify_validation_token(token, raw, dataset, tenant, user, fmt, row_count):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise ValidationError({"validation_token": "Validation token expired; run dry-run again."}) from exc
    except signing.BadSignature as exc:
        raise ValidationError({"validation_token": "Invalid validation token."}) from exc
    expected = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "dataset": dataset,
        "tenant": str(tenant.id),
        "user": str(user.pk),
        "format": fmt,
        "rows": row_count,
    }
    if payload != expected:
        raise ValidationError({"validation_token": "The file or validation context changed; run dry-run again."})


def export_rows(dataset, request, tenant):
    config = DATASETS[dataset]
    if dataset == "users":
        require_whole_tenant_permission(request.user, tenant, config["view_permission"])
        memberships = TenantMembership.objects.select_related("user").filter(tenant=tenant).order_by("user__username")
        return [{
            "username": m.user.username,
            "first_name": m.user.first_name,
            "last_name": m.user.last_name,
            "email": m.user.email,
            "membership_active": str(bool(m.is_active)).lower(),
        } for m in memberships]

    require_tenant_permission(request.user, tenant, config["view_permission"])
    allowed = set(accessible_organization_unit_ids(request.user, tenant, config["view_permission"]))

    if dataset == "organization":
        qs = OrganizationUnit.objects.for_tenant(tenant).filter(
            id__in=allowed, deleted_at__isnull=True
        ).select_related("parent", "manager").order_by("code")
        return [{
            "code": x.code, "name": x.name, "unit_type": x.unit_type,
            "parent_code": x.parent.code if x.parent_id else "", "name_en": x.name_en,
            "manager_username": x.manager.username if x.manager_id else "", "status": x.status,
        } for x in qs]

    if dataset == "assets":
        qs = Asset.objects.filter(
            tenant=tenant, deleted_at__isnull=True, organization_unit_id__in=allowed
        ).select_related("organization_unit", "owner", "custodian").order_by("code")
        return [{
            "code": x.code, "title": x.title, "asset_type": x.asset_type,
            "organization_code": x.organization_unit.code, "owner_username": x.owner.username,
            "custodian_username": x.custodian.username if x.custodian_id else "",
            "description": x.description, "confidentiality": x.confidentiality,
            "integrity": x.integrity, "availability": x.availability,
            "criticality": x.criticality, "status": x.status,
        } for x in qs]

    if dataset == "risks":
        qs = Risk.objects.filter(tenant=tenant, deleted_at__isnull=True).select_related(
            "organization_unit", "asset", "owner"
        )
        if not has_whole_tenant_permission(request.user, tenant, config["view_permission"]):
            qs = qs.filter(organization_unit_id__in=allowed)
        return [{
            "code": x.code, "title": x.title,
            "organization_code": x.organization_unit.code if x.organization_unit_id else "",
            "asset_code": x.asset.code if x.asset_id else "", "owner_username": x.owner.username,
            "status": x.status, "review_date": x.review_date.isoformat() if x.review_date else "",
            "scenario": x.scenario, "cause": x.cause, "consequence": x.consequence,
        } for x in qs.order_by("code")]

    qs = Control.objects.filter(tenant=tenant, deleted_at__isnull=True).select_related("category").order_by("code")
    return [{
        "code": x.code, "title": x.title, "description": x.description, "objective": x.objective,
        "control_type": x.control_type, "nature": x.nature, "frequency": x.frequency,
        "automation_level": x.automation_level, "status": x.status,
        "category_code": x.category.code if x.category_id else "",
    } for x in qs]

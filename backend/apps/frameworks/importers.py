import io
import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Framework, FrameworkVersion, Requirement, RequirementTranslation


REQUIRED_COLUMNS = {"code", "title"}
BASE_COLUMNS = {
    "code", "parent_code", "title", "body", "guidance", "assessable", "mandatory", "weight", "sort_order"
}


def _bool(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    if value in {"1", "true", "yes", "y", "بله"}:
        return True
    if value in {"0", "false", "no", "n", "خیر"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _decimal(value, default="1"):
    try:
        return str(Decimal(str(value if value not in (None, "") else default)))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value}") from exc


def _normalize_manifest(manifest):
    framework = manifest.get("framework") or {}
    version = manifest.get("version") or {}
    if not framework.get("code") or not framework.get("name"):
        raise ValidationError({"framework": "framework.code and framework.name are required."})
    if not version.get("version_code"):
        raise ValidationError({"version": "version.version_code is required."})
    return framework, version


def parse_json_pack(raw):
    try:
        data = json.loads(raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as exc:
        raise ValidationError({"file": f"Invalid JSON content pack: {exc}"}) from exc
    framework, version = _normalize_manifest(data)
    requirements = data.get("requirements") or []
    return normalize_rows(framework, version, requirements)


def parse_xlsx_pack(raw):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValidationError({"file": "openpyxl is required for XLSX imports."}) from exc
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationError({"file": f"Invalid XLSX file: {exc}"}) from exc
    if "requirements" not in workbook.sheetnames:
        raise ValidationError({"file": "XLSX pack must contain a 'requirements' sheet."})
    manifest = {}
    if "manifest" in workbook.sheetnames:
        for row in workbook["manifest"].iter_rows(values_only=True):
            if row and row[0] not in (None, ""):
                manifest[str(row[0]).strip()] = row[1] if len(row) > 1 else None
    framework = {
        "code": manifest.get("framework.code"),
        "name": manifest.get("framework.name"),
        "publisher": manifest.get("framework.publisher") or "",
        "framework_type": manifest.get("framework.framework_type") or "standard",
        "license_type": manifest.get("framework.license_type") or "customer_provided",
        "description": manifest.get("framework.description") or "",
    }
    version = {
        "version_code": manifest.get("version.version_code"),
        "title": manifest.get("version.title") or "",
        "publication_date": manifest.get("version.publication_date") or None,
        "effective_date": manifest.get("version.effective_date") or None,
    }
    _normalize_manifest({"framework": framework, "version": version})
    sheet = workbook["requirements"]
    rows = sheet.iter_rows(values_only=True)
    try:
        headers = [str(x).strip() if x is not None else "" for x in next(rows)]
    except StopIteration:
        raise ValidationError({"file": "requirements sheet is empty."})
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValidationError({"file": f"Missing required columns: {', '.join(sorted(missing))}"})
    records = []
    for row_number, row in enumerate(rows, start=2):
        record = {headers[i]: row[i] if i < len(row) else None for i in range(len(headers)) if headers[i]}
        if all(v in (None, "") for v in record.values()):
            continue
        record["_row"] = row_number
        records.append(record)
    return normalize_rows(framework, version, records)


def normalize_rows(framework, version, rows):
    errors = []
    normalized = []
    seen = set()
    translation_languages = set()
    for index, row in enumerate(rows, start=1):
        row_no = row.get("_row", index)
        code = str(row.get("code") or "").strip()
        title = str(row.get("title") or "").strip()
        if not code:
            errors.append({"row": row_no, "field": "code", "message": "code is required"})
            continue
        if not title:
            errors.append({"row": row_no, "field": "title", "message": "title is required"})
        if code in seen:
            errors.append({"row": row_no, "field": "code", "message": f"duplicate code: {code}"})
        seen.add(code)
        try:
            assessable = _bool(row.get("assessable"), True)
            mandatory = _bool(row.get("mandatory"), True)
            weight = _decimal(row.get("weight"), "1")
            sort_order = int(row.get("sort_order") or 0)
        except (ValueError, TypeError) as exc:
            errors.append({"row": row_no, "message": str(exc)})
            assessable, mandatory, weight, sort_order = True, True, "1", 0
        translations = []
        for key, value in row.items():
            if not key.startswith("title_") or value in (None, ""):
                continue
            language = key[6:]
            if not language:
                continue
            translation_languages.add(language)
            translations.append({
                "language": language,
                "title": str(value),
                "body": str(row.get(f"body_{language}") or ""),
                "guidance": str(row.get(f"guidance_{language}") or ""),
            })
        normalized.append({
            "code": code,
            "parent_code": str(row.get("parent_code") or "").strip() or None,
            "title": title,
            "body": str(row.get("body") or ""),
            "guidance": str(row.get("guidance") or ""),
            "assessable": assessable,
            "mandatory": mandatory,
            "weight": weight,
            "sort_order": sort_order,
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
            "translations": translations,
        })
    codes = {x["code"] for x in normalized}
    parent_by_code = {x["code"]: x.get("parent_code") for x in normalized}
    for item in normalized:
        if item["parent_code"] and item["parent_code"] not in codes:
            errors.append({"code": item["code"], "field": "parent_code", "message": f"parent code not found: {item['parent_code']}"})
    # Validate hierarchy cycles during dry-run so commit never discovers a cycle late.
    for code in codes:
        path = set()
        node = code
        while node and node in parent_by_code:
            if node in path:
                errors.append({"code": code, "field": "parent_code", "message": "requirement hierarchy contains a cycle"})
                break
            path.add(node)
            node = parent_by_code.get(node)
    # Deduplicate equivalent cycle errors while preserving deterministic output.
    unique_errors = []
    seen_errors = set()
    for error in errors:
        key = (error.get("row"), error.get("code"), error.get("field"), error.get("message"))
        if key not in seen_errors:
            unique_errors.append(error)
            seen_errors.add(key)
    errors = unique_errors
    return {
        "framework": framework,
        "version": version,
        "requirements": normalized,
        "errors": errors,
        "warnings": [],
        "languages": sorted(translation_languages),
    }


def parse_pack(uploaded_file):
    name = (getattr(uploaded_file, "name", "") or "").lower()
    raw = uploaded_file.read()
    if name.endswith(".json"):
        return parse_json_pack(raw)
    if name.endswith(".xlsx"):
        return parse_xlsx_pack(raw)
    raise ValidationError({"file": "Supported content-pack formats are .json and .xlsx."})


@transaction.atomic
def commit_pack(parsed, tenant, user):
    if parsed.get("errors"):
        raise ValidationError({"import": parsed["errors"]})
    fw_data = parsed["framework"]
    version_data = parsed["version"]
    framework, created = Framework.objects.get_or_create(
        tenant=tenant,
        code=fw_data["code"],
        defaults={
            "name": fw_data["name"],
            "publisher": fw_data.get("publisher", ""),
            "framework_type": fw_data.get("framework_type", "standard"),
            "content_source": Framework.ContentSource.IMPORTED,
            "license_type": fw_data.get("license_type", "customer_provided"),
            "license_metadata": fw_data.get("license_metadata") or {},
            "description": fw_data.get("description", ""),
            "status": Framework.Status.DRAFT,
            "created_by": user,
        },
    )
    if not created and framework.deleted_at is not None:
        raise ValidationError({"framework": "A framework with this code exists in archive."})
    if FrameworkVersion.objects.filter(framework=framework, version_code=version_data["version_code"]).exists():
        raise ValidationError({"version": "This framework version already exists."})
    version = FrameworkVersion.objects.create(
        framework=framework,
        version_code=version_data["version_code"],
        title=version_data.get("title", ""),
        publication_date=version_data.get("publication_date") or None,
        effective_date=version_data.get("effective_date") or None,
        status=FrameworkVersion.Status.DRAFT,
        metadata=version_data.get("metadata") or {},
        created_by=user,
    )
    req_by_code = {}
    for item in parsed["requirements"]:
        req = Requirement.objects.create(
            framework_version=version,
            code=item["code"],
            title=item["title"],
            body=item.get("body", ""),
            guidance=item.get("guidance", ""),
            assessable=item.get("assessable", True),
            mandatory=item.get("mandatory", True),
            weight=item.get("weight", "1"),
            sort_order=item.get("sort_order", 0),
            metadata=item.get("metadata") or {},
        )
        req_by_code[item["code"]] = req
        for tr in item.get("translations", []):
            RequirementTranslation.objects.create(requirement=req, **tr)
    for item in parsed["requirements"]:
        if item.get("parent_code"):
            req = req_by_code[item["code"]]
            req.parent = req_by_code[item["parent_code"]]
            req.save(update_fields=["parent", "updated_at"])
    return framework, version

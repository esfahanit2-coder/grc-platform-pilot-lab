import io
import json

from django.http import HttpResponse

from .services import canonical_version_payload
from .models import RequirementTranslation


def version_as_json_response(version):
    payload = canonical_version_payload(version)
    payload["framework_metadata"] = {
        "name": version.framework.name,
        "publisher": version.framework.publisher,
        "framework_type": version.framework.framework_type,
        "license_type": version.framework.license_type,
        "license_metadata": version.framework.license_metadata,
    }
    response = HttpResponse(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{version.framework.code}-{version.version_code}.json"'
    return response


def version_as_xlsx_response(version):
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for XLSX exports") from exc
    workbook = Workbook()
    manifest = workbook.active
    manifest.title = "manifest"
    entries = [
        ("framework.code", version.framework.code),
        ("framework.name", version.framework.name),
        ("framework.publisher", version.framework.publisher),
        ("framework.framework_type", version.framework.framework_type),
        ("framework.license_type", version.framework.license_type),
        ("framework.description", version.framework.description),
        ("version.version_code", version.version_code),
        ("version.title", version.title),
        ("version.publication_date", version.publication_date),
        ("version.effective_date", version.effective_date),
    ]
    for row in entries:
        manifest.append(row)
    sheet = workbook.create_sheet("requirements")
    languages = sorted(set(RequirementTranslation.objects.filter(requirement__framework_version=version).values_list("language", flat=True)))
    headers = ["code", "parent_code", "title", "body", "guidance", "assessable", "mandatory", "weight", "sort_order"]
    for lang in languages:
        headers.extend([f"title_{lang}", f"body_{lang}", f"guidance_{lang}"])
    sheet.append(headers)
    for req in version.requirements.prefetch_related("translations").select_related("parent").order_by("sort_order", "code"):
        translations = {tr.language: tr for tr in req.translations.all()}
        row = [req.code, req.parent.code if req.parent_id else "", req.title, req.body, req.guidance, req.assessable, req.mandatory, float(req.weight), req.sort_order]
        for lang in languages:
            tr = translations.get(lang)
            row.extend([tr.title if tr else "", tr.body if tr else "", tr.guidance if tr else ""])
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    response = HttpResponse(stream.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{version.framework.code}-{version.version_code}.xlsx"'
    return response

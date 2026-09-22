from django.db import transaction
from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.tenancy.services import resolve_tenant_for_request

from .data_exchange import (
    DATASETS,
    dataset_config,
    export_rows,
    make_validation_token,
    plan_import,
    read_upload,
    render_table,
    verify_validation_token,
)


def _download(payload, content_type, filename):
    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class DataExchangeCatalogView(APIView):
    def get(self, request):
        resolve_tenant_for_request(request)
        return Response({
            "datasets": {
                key: {
                    "label": value["label"],
                    "headers": value["headers"],
                    "formats": ["csv", "xlsx"],
                }
                for key, value in DATASETS.items()
            },
            "limits": {"max_rows": 5000, "max_upload_mb": 5, "validation_token_minutes": 30},
        })


class DataExchangeTemplateView(APIView):
    def get(self, request):
        resolve_tenant_for_request(request)
        dataset = str(request.query_params.get("dataset") or "").lower()
        config = dataset_config(dataset)
        fmt = str(request.query_params.get("format") or "xlsx").lower()
        payload, content_type = render_table(config["headers"], [], fmt)
        return _download(payload, content_type, f"{dataset}-import-template.{fmt}")


class DataExchangeExportView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        dataset = str(request.query_params.get("dataset") or "").lower()
        config = dataset_config(dataset)
        fmt = str(request.query_params.get("format") or "xlsx").lower()
        rows = export_rows(dataset, request, tenant)
        payload, content_type = render_table(config["headers"], rows, fmt)
        record_audit_event(
            request.user, tenant, "data_exchange.export", "data_exchange", tenant.id,
            metadata={"dataset": dataset, "format": fmt, "row_count": len(rows)}, request=request,
        )
        return _download(payload, content_type, f"{dataset}-export.{fmt}")


class DataExchangeValidateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        tenant = resolve_tenant_for_request(request)
        dataset = str(request.data.get("dataset") or "").lower()
        dataset_config(dataset)
        raw, fmt, rows = read_upload(request.FILES.get("file"), dataset)
        plan = plan_import(dataset, rows, request, tenant, apply=False)
        if plan["error_count"] == 0:
            plan["validation_token"] = make_validation_token(
                raw, dataset, tenant, request.user, fmt, len(rows)
            )
        else:
            plan["validation_token"] = None
        plan["format"] = fmt
        plan["preview"] = rows[:20]
        return Response(plan)


class DataExchangeCommitView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        tenant = resolve_tenant_for_request(request)
        dataset = str(request.data.get("dataset") or "").lower()
        dataset_config(dataset)
        raw, fmt, rows = read_upload(request.FILES.get("file"), dataset)
        verify_validation_token(
            request.data.get("validation_token"), raw, dataset, tenant, request.user, fmt, len(rows)
        )
        dry_plan = plan_import(dataset, rows, request, tenant, apply=False)
        if dry_plan["error_count"]:
            return Response({**dry_plan, "detail": "Data changed since validation; commit aborted."}, status=400)
        applied = plan_import(dataset, rows, request, tenant, apply=True)
        if applied["error_count"]:
            raise ValidationError({"import": "Atomic commit failed validation.", "results": applied["results"]})
        record_audit_event(
            request.user, tenant, "data_exchange.import", "data_exchange", tenant.id,
            metadata={
                "dataset": dataset, "format": fmt, "row_count": applied["row_count"],
                "create_count": applied["create_count"], "update_count": applied["update_count"],
            },
            request=request,
        )
        return Response({**applied, "committed": True})

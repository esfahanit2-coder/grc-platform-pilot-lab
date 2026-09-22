import secrets

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.services import require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request

from .operations import build_operational_status
from .operations_metrics import render_prometheus_metrics


class OperationsStatusView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "security.view")
        return Response(build_operational_status())


class OperationsMetricsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        configured = str(getattr(settings, "OPS_METRICS_TOKEN", "") or "")
        production = getattr(settings, "APP_ENV", "development") == "production"

        if production and not configured:
            return Response(
                {"detail": "Metrics endpoint is not configured."},
                status=503,
            )

        if configured:
            header = str(request.headers.get("Authorization") or "")
            prefix = "Bearer "
            supplied = header[len(prefix):] if header.startswith(prefix) else ""
            if not supplied or not secrets.compare_digest(supplied, configured):
                return Response({"detail": "Metrics authorization failed."}, status=403)

        payload = render_prometheus_metrics(build_operational_status())
        return HttpResponse(
            payload,
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )

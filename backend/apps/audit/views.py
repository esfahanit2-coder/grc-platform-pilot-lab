import json

from django.http import HttpResponse
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.services import require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request

from .models import AuditEvent
from .serializers import AuditEventSerializer


def _audit_filters(qs, params):
    if params.get("action"):
        qs = qs.filter(action=params["action"])
    if params.get("category"):
        qs = qs.filter(category=params["category"])
    if params.get("actor"):
        qs = qs.filter(actor_username__icontains=params["actor"])
    if params.get("object_type"):
        qs = qs.filter(object_type=params["object_type"])
    if params.get("outcome"):
        qs = qs.filter(outcome=params["outcome"])
    return qs


class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        tenant = resolve_tenant_for_request(self.request)
        require_whole_tenant_permission(self.request.user, tenant, "audit.view")
        qs = AuditEvent.objects.filter(tenant=tenant).select_related("actor")
        return _audit_filters(qs, self.request.query_params).order_by("-created_at")


def _siem_event(event):
    return {
        "schema_version": 1,
        "event_id": str(event.id),
        "created_at": event.created_at.isoformat(),
        "chain_sequence": event.chain_sequence,
        "request_id": str(event.request_id),
        "actor": event.actor_username or None,
        "action": event.action,
        "category": event.category,
        "outcome": event.outcome,
        "object_type": event.object_type,
        "object_id": str(event.object_id) if event.object_id else None,
        "http_method": event.http_method or None,
        "path": event.path or None,
        "integrity": {
            "previous_hash": event.previous_hash,
            "event_hash": event.event_hash,
            "key_id": event.integrity_key_id,
        },
    }


class AuditEventExportView(APIView):
    """Bounded SIEM export that omits customer payload fields by design."""

    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "audit.view")

        try:
            after = max(0, int(request.query_params.get("after_sequence") or 0))
            limit = int(request.query_params.get("limit") or 500)
        except (TypeError, ValueError) as exc:
            raise ValidationError("after_sequence and limit must be integers.") from exc
        if limit < 1 or limit > 1000:
            raise ValidationError("limit must be between 1 and 1000.")

        qs = AuditEvent.objects.filter(
            tenant=tenant,
            chain_sequence__gt=after,
        ).select_related("actor")
        qs = _audit_filters(qs, request.query_params).order_by("chain_sequence")

        rows = list(qs[: limit + 1])
        has_more = len(rows) > limit
        rows = rows[:limit]
        events = [_siem_event(row) for row in rows]
        next_after = rows[-1].chain_sequence if rows else after

        if str(request.query_params.get("format") or "").lower() == "jsonl":
            body = "".join(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                for event in events
            )
            response = HttpResponse(body, content_type="application/x-ndjson; charset=utf-8")
            response["X-GRC-Next-After-Sequence"] = str(next_after)
            response["X-GRC-Has-More"] = "1" if has_more else "0"
            return response

        return Response(
            {
                "schema_version": 1,
                "events": events,
                "next_after_sequence": next_after,
                "has_more": has_more,
            }
        )

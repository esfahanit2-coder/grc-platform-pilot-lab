import hashlib
import hmac
import json
import os
from datetime import timezone as dt_timezone

from django.conf import settings

AUDIT_CHAIN_SCHEMA = "grc-audit-chain-v1"
GENESIS_HASH = "0" * 64


class AuditIntegrityConfigurationError(RuntimeError):
    pass


def current_integrity_key_id() -> str:
    value = str(
        getattr(settings, "AUDIT_INTEGRITY_KEY_ID", "")
        or os.getenv("AUDIT_INTEGRITY_KEY_ID", "v1")
        or ""
    ).strip()
    if not value or len(value) > 64:
        raise AuditIntegrityConfigurationError("AUDIT_INTEGRITY_KEY_ID must be 1..64 characters")
    return value


def integrity_key_bytes(key_id: str | None = None) -> bytes:
    expected_id = current_integrity_key_id()
    requested_id = key_id or expected_id
    if requested_id != expected_id:
        raise AuditIntegrityConfigurationError(
            f"integrity key id {requested_id!r} is not available in this deployment"
        )

    configured = str(
        getattr(settings, "AUDIT_INTEGRITY_KEY", "")
        or os.getenv("AUDIT_INTEGRITY_KEY", "")
        or ""
    )
    app_env = str(getattr(settings, "APP_ENV", "development") or "development").strip().lower()
    if app_env == "production" and not configured:
        raise AuditIntegrityConfigurationError(
            "AUDIT_INTEGRITY_KEY is required when APP_ENV=production; do not reuse DJANGO_SECRET_KEY"
        )

    value = configured or str(settings.SECRET_KEY)
    if len(value.encode("utf-8")) < 32:
        raise AuditIntegrityConfigurationError("AUDIT_INTEGRITY_KEY must contain at least 32 bytes")
    return value.encode("utf-8")


def scope_key_for_tenant_id(tenant_id) -> str:
    return f"tenant:{tenant_id}" if tenant_id else "global"


def canonical_timestamp(value) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).isoformat(timespec="microseconds")


def canonical_event_payload(event) -> dict:
    return {
        "schema": AUDIT_CHAIN_SCHEMA,
        "id": str(event.id),
        "tenant_id": str(event.tenant_id) if event.tenant_id else "",
        # actor_id is intentionally excluded: the historical username snapshot
        # is immutable while the FK may legitimately become NULL on user delete.
        "actor_username": event.actor_username or "",
        "action": event.action,
        "category": event.category,
        "outcome": event.outcome,
        "object_type": event.object_type,
        "object_id": str(event.object_id) if event.object_id else "",
        "object_repr": event.object_repr or "",
        "metadata": event.metadata or {},
        "old_data": event.old_data or {},
        "new_data": event.new_data or {},
        "ip_address": str(event.ip_address) if event.ip_address else "",
        "user_agent": event.user_agent or "",
        "http_method": event.http_method or "",
        "path": event.path or "",
        "request_id": str(event.request_id),
        "created_at": canonical_timestamp(event.created_at),
        "chain_sequence": int(event.chain_sequence),
        "previous_hash": event.previous_hash or GENESIS_HASH,
        "integrity_key_id": event.integrity_key_id,
    }


def canonical_event_bytes(event) -> bytes:
    return json.dumps(
        canonical_event_payload(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_event_hash(event) -> str:
    key = integrity_key_bytes(event.integrity_key_id)
    return hmac.new(key, canonical_event_bytes(event), hashlib.sha256).hexdigest()

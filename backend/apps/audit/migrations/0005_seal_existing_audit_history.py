import hashlib
import hmac
import json
import os
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import migrations


AUDIT_CHAIN_SCHEMA = "grc-audit-chain-v1"
GENESIS_HASH = "0" * 64


def _canonical_timestamp(value):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).isoformat(timespec="microseconds")


def _key_material():
    key_id = str(
        getattr(settings, "AUDIT_INTEGRITY_KEY_ID", "")
        or os.getenv("AUDIT_INTEGRITY_KEY_ID", "v1")
        or ""
    ).strip()
    if not key_id or len(key_id) > 64:
        raise RuntimeError("AUDIT_INTEGRITY_KEY_ID must be 1..64 characters before sealing audit history")

    configured = str(
        getattr(settings, "AUDIT_INTEGRITY_KEY", "")
        or os.getenv("AUDIT_INTEGRITY_KEY", "")
        or ""
    )
    app_env = str(getattr(settings, "APP_ENV", "development") or "development").strip().lower()
    if app_env == "production" and not configured:
        raise RuntimeError("AUDIT_INTEGRITY_KEY is required in production before sealing audit history")

    value = configured or str(settings.SECRET_KEY)
    encoded = value.encode("utf-8")
    if len(encoded) < 32:
        raise RuntimeError("AUDIT_INTEGRITY_KEY must contain at least 32 bytes before sealing audit history")
    return key_id, encoded


def _canonical_event_bytes(event):
    payload = {
        "schema": AUDIT_CHAIN_SCHEMA,
        "id": str(event.id),
        "tenant_id": str(event.tenant_id) if event.tenant_id else "",
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
        "created_at": _canonical_timestamp(event.created_at),
        "chain_sequence": int(event.chain_sequence),
        "previous_hash": event.previous_hash or GENESIS_HASH,
        "integrity_key_id": event.integrity_key_id,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def seal_existing_audit_history(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    AuditChainState = apps.get_model("audit", "AuditChainState")
    database = schema_editor.connection.alias
    key_id, key = _key_material()

    events = AuditEvent.objects.using(database)

    # Remove positive sequence values first so resequencing cannot transiently
    # collide with the conditional unique constraints introduced in 0004.
    # The migration is atomic on supported production PostgreSQL deployments.
    events.update(
        chain_sequence=0,
        previous_hash=GENESIS_HASH,
        event_hash="",
        integrity_key_id="",
    )

    tenant_ids = list(events.order_by().values_list("tenant_id", flat=True).distinct())
    tenant_ids.sort(key=lambda value: "" if value is None else str(value))

    for tenant_id in tenant_ids:
        previous_hash = GENESIS_HASH
        sequence = 0
        scope_events = events.filter(tenant_id=tenant_id).order_by("created_at", "id")

        for event in scope_events.iterator():
            sequence += 1
            event.chain_sequence = sequence
            event.previous_hash = previous_hash
            event.integrity_key_id = key_id
            event.event_hash = hmac.new(key, _canonical_event_bytes(event), hashlib.sha256).hexdigest()
            events.filter(pk=event.pk).update(
                chain_sequence=event.chain_sequence,
                previous_hash=event.previous_hash,
                integrity_key_id=event.integrity_key_id,
                event_hash=event.event_hash,
            )
            previous_hash = event.event_hash

        scope_key = f"tenant:{tenant_id}" if tenant_id else "global"
        AuditChainState.objects.using(database).update_or_create(
            scope_key=scope_key,
            defaults={
                "tenant_id": tenant_id,
                "sequence": sequence,
                "last_hash": previous_hash,
            },
        )


def preserve_sealed_history_on_reverse(apps, schema_editor):
    # Deliberate monotonic reverse: 0004 understands sealed fields and can
    # continue from the resulting chain head. Unsealing during rollback would
    # weaken integrity and is unnecessary for application compatibility.
    pass


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("audit", "0004_audit_integrity_chain"),
    ]

    operations = [
        migrations.RunPython(
            seal_existing_audit_history,
            preserve_sealed_history_on_reverse,
        ),
    ]

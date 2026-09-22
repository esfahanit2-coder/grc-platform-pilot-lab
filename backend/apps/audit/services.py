from django.db import transaction

from .integrity import GENESIS_HASH, compute_event_hash, current_integrity_key_id, scope_key_for_tenant_id
from .models import AuditChainState, AuditEvent


def _client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _category_from_action(action):
    return action.split(".", 1)[0] if "." in action else "application"


def record_audit_event(
    actor,
    tenant,
    action,
    object_type,
    object_id=None,
    metadata=None,
    request=None,
    *,
    old_data=None,
    new_data=None,
    object_repr="",
    outcome="success",
    category=None,
):
    username = ""
    if actor is not None:
        username = getattr(actor, "get_username", lambda: "")() or ""
    request_id = getattr(request, "correlation_id", None) if request else None
    tenant_id = getattr(tenant, "id", None)
    scope_key = scope_key_for_tenant_id(tenant_id)

    with transaction.atomic():
        # get_or_create handles the first writer race through the scope_key PK;
        # the subsequent SELECT FOR UPDATE serializes sequence/head advancement.
        AuditChainState.objects.get_or_create(
            scope_key=scope_key,
            defaults={
                "tenant": tenant,
                "sequence": 0,
                "last_hash": GENESIS_HASH,
            },
        )
        state = AuditChainState.objects.select_for_update().get(scope_key=scope_key)
        if state.tenant_id != tenant_id:
            raise RuntimeError("Audit chain scope/tenant mismatch; integrity state requires investigation.")

        kwargs = {}
        if request_id:
            kwargs["request_id"] = request_id
        event = AuditEvent(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            actor_username=username,
            tenant=tenant,
            action=action,
            category=category or _category_from_action(action),
            outcome=outcome,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            metadata=metadata or {},
            old_data=old_data or {},
            new_data=new_data or {},
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
            http_method=request.method if request else "",
            path=request.path[:500] if request else "",
            chain_sequence=state.sequence + 1,
            previous_hash=state.last_hash or GENESIS_HASH,
            integrity_key_id=current_integrity_key_id(),
            **kwargs,
        )
        event.event_hash = compute_event_hash(event)
        event.save(force_insert=True)

        state.sequence = event.chain_sequence
        state.last_hash = event.event_hash
        state.save(update_fields=["sequence", "last_hash", "updated_at"])
        return event

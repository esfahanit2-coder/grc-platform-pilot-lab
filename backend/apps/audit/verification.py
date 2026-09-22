from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from .integrity import AuditIntegrityConfigurationError, GENESIS_HASH, compute_event_hash, scope_key_for_tenant_id
from .models import AuditChainState, AuditEvent


REPORT_SCHEMA = "grc-audit-integrity-report-v1"


@dataclass(frozen=True)
class AuditIntegrityFinding:
    code: str
    message: str
    event_id: str | None = None
    sequence: int | None = None
    expected: str | int | None = None
    actual: str | int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "expected": self.expected,
            "actual": self.actual,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class AuditIntegrityResult:
    scope_key: str
    tenant_id: str | None
    event_count: int
    state_sequence: int | None
    state_last_hash: str | None
    findings: tuple[AuditIntegrityFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_key": self.scope_key,
            "tenant_id": self.tenant_id,
            "ok": self.ok,
            "event_count": self.event_count,
            "state": {
                "sequence": self.state_sequence,
                "last_hash": self.state_last_hash,
            },
            "findings": [finding.as_dict() for finding in self.findings],
        }


def verify_audit_scope(tenant_id=None) -> AuditIntegrityResult:
    scope_key = scope_key_for_tenant_id(tenant_id)
    findings: list[AuditIntegrityFinding] = []
    events = list(
        AuditEvent.system_objects.filter(tenant_id=tenant_id).order_by(
            "chain_sequence",
            "created_at",
            "id",
        )
    )

    previous_sequence = 0
    previous_hash = GENESIS_HASH

    for event in events:
        sequence = int(event.chain_sequence)
        expected_sequence = previous_sequence + 1
        if sequence != expected_sequence:
            findings.append(
                AuditIntegrityFinding(
                    code="sequence_mismatch",
                    message="Audit sequence is not contiguous for this scope.",
                    event_id=str(event.id),
                    sequence=sequence,
                    expected=expected_sequence,
                    actual=sequence,
                )
            )

        if not event.integrity_key_id or not event.event_hash or sequence < 1:
            findings.append(
                AuditIntegrityFinding(
                    code="unsealed_event",
                    message="Audit event is missing one or more required integrity fields.",
                    event_id=str(event.id),
                    sequence=sequence,
                )
            )

        if event.previous_hash != previous_hash:
            findings.append(
                AuditIntegrityFinding(
                    code="previous_hash_mismatch",
                    message="Audit event does not reference the preceding stored event hash.",
                    event_id=str(event.id),
                    sequence=sequence,
                    expected=previous_hash,
                    actual=event.previous_hash,
                )
            )

        try:
            expected_event_hash = compute_event_hash(event)
        except AuditIntegrityConfigurationError as exc:
            findings.append(
                AuditIntegrityFinding(
                    code="integrity_key_unavailable",
                    message=str(exc),
                    event_id=str(event.id),
                    sequence=sequence,
                    actual=event.integrity_key_id or None,
                )
            )
        else:
            if not hmac.compare_digest(event.event_hash or "", expected_event_hash):
                findings.append(
                    AuditIntegrityFinding(
                        code="event_hash_mismatch",
                        message="Stored audit event hash does not match the canonical event payload.",
                        event_id=str(event.id),
                        sequence=sequence,
                        expected=expected_event_hash,
                        actual=event.event_hash or "",
                    )
                )

        previous_sequence = sequence
        previous_hash = event.event_hash or ""

    state = AuditChainState.objects.filter(scope_key=scope_key).first()
    if events and state is None:
        findings.append(
            AuditIntegrityFinding(
                code="chain_state_missing",
                message="Audit events exist but the chain-head state row is missing.",
            )
        )
    elif state is not None:
        if state.tenant_id != tenant_id:
            findings.append(
                AuditIntegrityFinding(
                    code="chain_state_scope_mismatch",
                    message="Chain-head state is associated with the wrong tenant scope.",
                    expected=str(tenant_id) if tenant_id else "global",
                    actual=str(state.tenant_id) if state.tenant_id else "global",
                )
            )

        expected_head_sequence = previous_sequence if events else 0
        expected_head_hash = previous_hash if events else GENESIS_HASH
        if int(state.sequence) != expected_head_sequence:
            findings.append(
                AuditIntegrityFinding(
                    code="chain_head_sequence_mismatch",
                    message="Stored chain-head sequence does not match the final audit event.",
                    expected=expected_head_sequence,
                    actual=int(state.sequence),
                )
            )
        if not hmac.compare_digest(state.last_hash or "", expected_head_hash):
            findings.append(
                AuditIntegrityFinding(
                    code="chain_head_hash_mismatch",
                    message="Stored chain-head hash does not match the final audit event.",
                    expected=expected_head_hash,
                    actual=state.last_hash or "",
                )
            )

    return AuditIntegrityResult(
        scope_key=scope_key,
        tenant_id=str(tenant_id) if tenant_id else None,
        event_count=len(events),
        state_sequence=int(state.sequence) if state is not None else None,
        state_last_hash=state.last_hash if state is not None else None,
        findings=tuple(findings),
    )


def audit_scope_tenant_ids() -> list:
    tenant_ids = set(
        AuditEvent.system_objects.order_by().values_list("tenant_id", flat=True).distinct()
    )
    tenant_ids.update(
        AuditChainState.objects.order_by().values_list("tenant_id", flat=True).distinct()
    )
    return sorted(tenant_ids, key=lambda value: "" if value is None else str(value))


def verify_all_audit_chains() -> tuple[AuditIntegrityResult, ...]:
    return tuple(verify_audit_scope(tenant_id) for tenant_id in audit_scope_tenant_ids())


def build_verification_report(results) -> dict[str, Any]:
    normalized = tuple(results)
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": timezone.now().isoformat(),
        "ok": all(result.ok for result in normalized),
        "scope_count": len(normalized),
        "event_count": sum(result.event_count for result in normalized),
        "results": [result.as_dict() for result in normalized],
    }

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "grc-final-release-acceptance-v1"
ATTESTATION_SCHEMA = "grc-final-release-attestations-v1"
PILOT_SCHEMA = "grc-pilot-acceptance-evidence-v1"
PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"

REQUIRED_EXTERNAL_GATES = (
    "authorized_content_issue_5",
    "live_connectors_issue_6",
    "security_acceptance_issue_8",
    "visual_pilot_issue_42",
    "operator_runbook",
    "support_handover",
    "customer_uat_signoff",
)

REQUIRED_UAT_JOURNEYS = (
    "tenant_onboarding_and_mfa",
    "framework_content_import",
    "asset_risk_treatment",
    "control_evidence_assessment",
    "finding_capa_action",
    "internal_audit_and_control_testing",
    "controlled_document_approval",
    "workflow_assignment_transition",
    "reporting_preview_export",
    "work_center",
    "administration_scope_and_audit",
    "customer_import_export",
    "backup_restore_upgrade_support",
    "notifications_smtp",
    "executive_dashboard",
)

SECRETISH = re.compile(
    r"(?i)(password\s*[:=]|passwd\s*[:=]|secret\s*[:=]|token\s*[:=]|"
    r"api[_-]?key\s*[:=]|authorization\s*[:=]|bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"-----BEGIN [^-]*PRIVATE KEY-----)"
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
URI_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/@\s]+@")
PLACEHOLDER_MARKERS = ("REPLACE_WITH_", "PLACEHOLDER", "TBD")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "command-not-found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, "", "command-timeout")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def secret_safe_text(value: Any, *, max_len: int = 1000) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= max_len
        and not SECRETISH.search(value)
        and not URI_USERINFO.search(value.strip())
    )


def is_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    upper = value.strip().upper()
    return not upper or any(marker in upper for marker in PLACEHOLDER_MARKERS)


def valid_observed_at(value: Any) -> bool:
    if not isinstance(value, str) or is_placeholder(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def valid_evidence_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) <= 20
        and all(secret_safe_text(item, max_len=500) and not is_placeholder(item) for item in value)
    )


def validate_attestation(entry: Any) -> tuple[str, str]:
    if not isinstance(entry, dict):
        return BLOCKED, "attestation is missing"
    status = entry.get("status")
    if status not in {PASS, FAIL}:
        return BLOCKED, "status must be PASS or FAIL"
    if not secret_safe_text(entry.get("reviewer"), max_len=200) or is_placeholder(entry.get("reviewer")):
        return BLOCKED, "reviewer is missing, placeholder-like, or unsafe"
    if not valid_observed_at(entry.get("observed_at")):
        return BLOCKED, "observed_at must be a real timezone-aware ISO timestamp"
    if not secret_safe_text(entry.get("note"), max_len=1000):
        return BLOCKED, "note is missing or unsafe"
    if not valid_evidence_refs(entry.get("evidence_refs")):
        return BLOCKED, "at least one safe evidence reference is required"
    return status, "valid attestation"


def sanitize_attestation(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": entry["status"],
        "reviewer": entry["reviewer"].strip(),
        "observed_at": entry["observed_at"].strip(),
        "note": entry["note"].strip(),
        "evidence_refs": [item.strip() for item in entry["evidence_refs"]],
    }


def pilot_release_commit(summary: dict[str, Any]) -> str | None:
    checks = summary.get("checks")
    if not isinstance(checks, dict):
        return None
    item = checks.get("release_commit")
    if not isinstance(item, dict) or item.get("status") != PASS:
        return None
    details = item.get("details")
    if not isinstance(details, dict):
        return None
    commit = details.get("commit")
    return commit if isinstance(commit, str) and SHA40.fullmatch(commit) else None


def current_git_state() -> tuple[str | None, bool]:
    head = run(["git", "rev-parse", "HEAD"])
    status = run(["git", "status", "--porcelain", "--untracked-files=no"])
    sha = head.stdout.strip() if head.returncode == 0 and SHA40.fullmatch(head.stdout.strip()) else None
    return sha, status.returncode == 0 and not status.stdout.strip()


def evaluate(pilot: dict[str, Any], attestations: dict[str, Any], expected_sha: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    blockers: list[str] = []

    if pilot.get("schema") != PILOT_SCHEMA:
        checks["clean_host_issue_7"] = {"status": BLOCKED, "reason": "unsupported pilot summary schema"}
        blockers.append("clean_host_issue_7")
    else:
        pilot_sha = pilot_release_commit(pilot)
        pilot_ready = pilot.get("ready_to_close_issue_7") is True
        pilot_match = pilot_sha == expected_sha
        pilot_checks = pilot.get("checks") if isinstance(pilot.get("checks"), dict) else {}
        required = pilot.get("issue7_required_checks")
        missing = pilot.get("issue7_missing_or_failed")
        required_complete = (
            isinstance(required, list)
            and bool(required)
            and all(
                isinstance(name, str)
                and isinstance(pilot_checks.get(name), dict)
                and pilot_checks[name].get("status") == PASS
                for name in required
            )
        )
        missing_empty = isinstance(missing, list) and not missing
        status = PASS if pilot_ready and pilot_match and required_complete and missing_empty else FAIL
        checks["clean_host_issue_7"] = {
            "status": status,
            "pilot_ready_to_close_issue_7": pilot_ready,
            "pilot_release_sha_matches_candidate": pilot_match,
            "pilot_required_checks_complete": required_complete,
            "pilot_missing_or_failed_empty": missing_empty,
            "pilot_release_sha": pilot_sha,
        }
        if status != PASS:
            blockers.append("clean_host_issue_7")

    if attestations.get("schema") != ATTESTATION_SCHEMA:
        checks["attestations_schema"] = {"status": BLOCKED, "reason": "unsupported attestation schema"}
        blockers.append("attestations_schema")
        gate_entries: dict[str, Any] = {}
        journey_entries: dict[str, Any] = {}
    else:
        gate_entries = attestations.get("gates") if isinstance(attestations.get("gates"), dict) else {}
        journey_entries = attestations.get("uat_journeys") if isinstance(attestations.get("uat_journeys"), dict) else {}

    sanitized_gates: dict[str, Any] = {}
    for name in REQUIRED_EXTERNAL_GATES:
        entry = gate_entries.get(name)
        status, reason = validate_attestation(entry)
        if status in {PASS, FAIL}:
            sanitized_gates[name] = sanitize_attestation(entry)
        else:
            sanitized_gates[name] = {"status": BLOCKED, "reason": reason}
        checks[name] = {"status": status, "reason": reason}
        if status != PASS:
            blockers.append(name)

    sanitized_journeys: dict[str, Any] = {}
    for name in REQUIRED_UAT_JOURNEYS:
        entry = journey_entries.get(name)
        status, reason = validate_attestation(entry)
        if status in {PASS, FAIL}:
            sanitized_journeys[name] = sanitize_attestation(entry)
        else:
            sanitized_journeys[name] = {"status": BLOCKED, "reason": reason}
        checks[f"uat:{name}"] = {"status": status, "reason": reason}
        if status != PASS:
            blockers.append(f"uat:{name}")

    declared_sha = attestations.get("release_sha")
    release_identity_ok = isinstance(declared_sha, str) and declared_sha == expected_sha
    checks["attested_release_identity"] = {
        "status": PASS if release_identity_ok else FAIL,
        "declared_release_sha": declared_sha if isinstance(declared_sha, str) else None,
    }
    if not release_identity_ok:
        blockers.append("attested_release_identity")

    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "release_sha": expected_sha,
        "promotion_ready": not blockers,
        "blockers": blockers,
        "checks": checks,
        "sanitized_attestations": {
            "schema": ATTESTATION_SCHEMA,
            "release_sha": declared_sha if isinstance(declared_sha, str) else None,
            "gates": sanitized_gates,
            "uat_journeys": sanitized_journeys,
        },
        "promotion_boundary": (
            "promotion_ready=true only means the supplied exact-release evidence and human attestations "
            "satisfy this repository gate. It does not create or substitute the underlying legal, live-system, "
            "recovery, visual, security, or customer-UAT evidence."
        ),
    }


def secure_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def self_test() -> None:
    sha = "a" * 40
    valid = {
        "status": PASS,
        "reviewer": "reviewer-1",
        "observed_at": "2026-09-21T00:00:00Z",
        "note": "Reviewed against retained acceptance evidence.",
        "evidence_refs": ["ticket:123"],
    }
    pilot_required = ["release_commit", "core_services_healthy"]
    pilot = {
        "schema": PILOT_SCHEMA,
        "ready_to_close_issue_7": True,
        "issue7_required_checks": pilot_required,
        "issue7_missing_or_failed": [],
        "checks": {
            "release_commit": {"status": PASS, "details": {"commit": sha}},
            "core_services_healthy": {"status": PASS},
        },
    }
    attestations = {
        "schema": ATTESTATION_SCHEMA,
        "release_sha": sha,
        "gates": {name: dict(valid) for name in REQUIRED_EXTERNAL_GATES},
        "uat_journeys": {name: dict(valid) for name in REQUIRED_UAT_JOURNEYS},
    }
    complete = evaluate(pilot, attestations, sha)
    assert complete["promotion_ready"] is True
    assert complete["blockers"] == []

    wrong_release = evaluate(pilot, {**attestations, "release_sha": "b" * 40}, sha)
    assert wrong_release["promotion_ready"] is False
    assert "attested_release_identity" in wrong_release["blockers"]

    incomplete = json.loads(json.dumps(attestations))
    incomplete["gates"]["security_acceptance_issue_8"]["status"] = FAIL
    failed = evaluate(pilot, incomplete, sha)
    assert failed["promotion_ready"] is False
    assert "security_acceptance_issue_8" in failed["blockers"]

    unsafe = json.loads(json.dumps(attestations))
    unsafe["gates"]["operator_runbook"]["note"] = "password=must-not-survive"
    blocked = evaluate(pilot, unsafe, sha)
    assert blocked["promotion_ready"] is False
    assert blocked["sanitized_attestations"]["gates"]["operator_runbook"]["status"] == BLOCKED
    assert "must-not-survive" not in json.dumps(blocked)

    placeholders = json.loads(json.dumps(attestations))
    placeholders["gates"]["operator_runbook"]["reviewer"] = "REPLACE_WITH_REVIEWER"
    placeholders["gates"]["operator_runbook"]["evidence_refs"] = ["REPLACE_WITH_REFERENCE"]
    placeholder_result = evaluate(pilot, placeholders, sha)
    assert placeholder_result["promotion_ready"] is False
    assert "operator_runbook" in placeholder_result["blockers"]

    bad_time = json.loads(json.dumps(attestations))
    bad_time["gates"]["operator_runbook"]["observed_at"] = "2026-09-21"
    bad_time_result = evaluate(pilot, bad_time, sha)
    assert bad_time_result["promotion_ready"] is False

    userinfo = json.loads(json.dumps(attestations))
    userinfo["gates"]["operator_runbook"]["evidence_refs"] = ["ticket mirrors https://user:pass@example.invalid/ticket/1"]
    userinfo_result = evaluate(pilot, userinfo, sha)
    assert userinfo_result["promotion_ready"] is False

    inconsistent_pilot = json.loads(json.dumps(pilot))
    inconsistent_pilot["checks"]["core_services_healthy"]["status"] = FAIL
    inconsistent_pilot_result = evaluate(inconsistent_pilot, attestations, sha)
    assert inconsistent_pilot_result["promotion_ready"] is False
    assert "clean_host_issue_7" in inconsistent_pilot_result["blockers"]

    print("final release acceptance self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate exact-release datacenter/UAT evidence into a fail-closed RC promotion decision.")
    parser.add_argument("--pilot-summary", type=Path, help="Issue #7 low-risk acceptance-summary.json.")
    parser.add_argument("--attestations", type=Path, help="Completed final-release attestation JSON.")
    parser.add_argument("--release-sha", help="Exact candidate Git SHA. Defaults to current HEAD.")
    parser.add_argument("--out", type=Path, help="Output JSON path; defaults to artifacts/final-release-acceptance.json.")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    if not args.pilot_summary or not args.attestations:
        print("ERROR: --pilot-summary and --attestations are required", file=sys.stderr)
        return 2

    head, clean = current_git_state()
    expected_sha = args.release_sha or head
    if not isinstance(expected_sha, str) or not SHA40.fullmatch(expected_sha):
        print("ERROR: a valid 40-character release SHA is required", file=sys.stderr)
        return 2

    try:
        pilot = load_json(args.pilot_summary)
        attestations = load_json(args.attestations)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = evaluate(pilot, attestations, expected_sha)
    result["repository_checkout"] = {
        "head_sha": head,
        "head_matches_release": head == expected_sha,
        "tracked_checkout_clean": clean,
    }
    if head != expected_sha or not clean:
        result["promotion_ready"] = False
        if head != expected_sha:
            result["blockers"].append("repository_head_matches_release")
        if not clean:
            result["blockers"].append("repository_tracked_checkout_clean")

    output = args.out or Path("artifacts/final-release-acceptance.json")
    secure_json(output, result)
    print(json.dumps({
        "schema": result["schema"],
        "release_sha": expected_sha,
        "promotion_ready": result["promotion_ready"],
        "blockers": result["blockers"],
        "output": str(output),
    }, sort_keys=True))
    if args.require_complete and not result["promotion_ready"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

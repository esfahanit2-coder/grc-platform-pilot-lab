#!/usr/bin/env python3
"""Collect low-risk, reviewable evidence for the real clean-host pilot drill.

This tool intentionally separates automated observations from operator attestations.
It never reads or copies .env contents, private keys, backup payloads, customer data,
service logs, or AI prompt/response bodies into the acceptance bundle.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import ssl
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

SCHEMA = "grc-pilot-acceptance-evidence-v1"
MANUAL_SCHEMA = "grc-pilot-manual-observations-v1"
AI_SCHEMA = "grc-ai-adversarial-evaluation-v1"
PASS = "PASS"
FAIL = "FAIL"
NOT_MEASURED = "NOT_MEASURED"
MANUAL_REQUIRED = "MANUAL_REQUIRED"
ALLOWED_MANUAL_STATUS = {PASS, FAIL}

MANUAL_KEYS = (
    "clean_host_confirmed",
    "https_secure_cookie_csrf",
    "restore_marker_proof",
    "object_evidence_checksum",
    "internet_egress_blocked_during_ai",
    "ai_disable_provider_switch",
    "monitoring_logging_health",
    "rpo_accepted",
    "rto_accepted",
    "ai_human_review",
    "scanner_real_validation",
    "audit_immutable_storage_validation",
    "pentest_completed_or_scheduled",
)

ISSUE7_REQUIRED = (
    "release_commit",
    "release_checkout_clean",
    "clean_host_confirmed",
    "core_services_healthy",
    "tls_endpoint",
    "https_secure_cookie_csrf",
    "backup_observation",
    "restore_observation",
    "restore_marker_proof",
    "object_evidence_checksum",
    "rpo_accepted",
    "rto_accepted",
    "local_ai_generation_embedding",
    "internet_egress_blocked_during_ai",
    "ai_disable_provider_switch",
    "monitoring_logging_health",
)

EXCLUDED_BY_DESIGN = (
    ".env contents and environment-variable dumps",
    "TLS private keys and certificate PEM bodies",
    "database dumps, object-store archives and customer payloads",
    "application/service logs",
    "connector credentials, tokens and authorization headers",
    "AI prompts, model responses and synthetic canary values",
    "secret-bearing backup config.env",
)

SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|secret[_-]?key)\s*[:=]\s*\S+"
)
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
URI_USERINFO = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_text(value: str, limit: int = 12000) -> str:
    text = value or ""
    text = PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", text)
    text = URI_USERINFO.sub(r"\1[REDACTED]@", text)
    text = SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = BEARER.sub("Bearer [REDACTED]", text)
    if len(text) > limit:
        text = text[:limit] + "\n...[TRUNCATED]\n"
    return text


def secure_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def secure_json(path: Path, payload: Any) -> None:
    secure_write(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def check(status: str, source: str, note: str = "", **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, "source": source}
    if note:
        payload["note"] = sanitize_text(note, 1000)
    if details:
        payload["details"] = details
    return payload


def run_command(command: list[str], timeout: int = 90) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout or "", completed.stderr or ""
    except FileNotFoundError as exc:
        return None, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return None, stdout, f"timeout: {stderr}"


def status_from_exit(code: int | None, *, unavailable_is_not_measured: bool = True) -> str:
    if code == 0:
        return PASS
    if code is None and unavailable_is_not_measured:
        return NOT_MEASURED
    return FAIL


def collect_os_metadata() -> dict[str, Any]:
    result: dict[str, Any] = {
        "system": platform.system(),
        "machine": platform.machine(),
    }
    path = Path("/etc/os-release")
    if path.is_file():
        allowed = {"ID", "VERSION_ID", "NAME", "PRETTY_NAME"}
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key in allowed:
                result[key.lower()] = value.strip().strip('"')
    return result


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def validate_backup_observation(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if payload is None:
        return check(NOT_MEASURED, "backup-observation", "No backup observation was supplied."), None
    name = payload.get("backup_name")
    duration = payload.get("duration_seconds")
    started = payload.get("started_at")
    completed = payload.get("completed_at")
    if not isinstance(name, str) or not name or not isinstance(duration, int) or duration < 0 or not started or not completed:
        return check(FAIL, "backup-observation", "Backup observation is malformed or incomplete."), None
    sanitized = {
        "backup_name": name,
        "started_at": str(started),
        "completed_at": str(completed),
        "duration_seconds": duration,
        "release_consistent_quiesce": bool(payload.get("release_consistent_quiesce")),
        "contains_secret_bearing_config": bool(payload.get("contains_secret_bearing_config")),
        "tls_private_key_included": bool(payload.get("tls_private_key_included")),
    }
    return check(PASS, "backup-observation", "Backup observation is structurally valid.", duration_seconds=duration), sanitized


def validate_restore_observation(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if payload is None:
        return check(NOT_MEASURED, "restore-observation", "No restore observation was supplied."), None
    name = payload.get("backup_name")
    rto = payload.get("observed_rto_seconds")
    started = payload.get("restore_started_at")
    ready_at = payload.get("service_readiness_confirmed_at")
    if not isinstance(name, str) or not name or not isinstance(rto, int) or rto < 0 or not started or not ready_at:
        return check(FAIL, "restore-observation", "Restore observation is malformed or incomplete."), None
    sanitized = {
        "backup_name": name,
        "backup_source_commit": str(payload.get("backup_source_commit") or ""),
        "restore_checkout_commit": str(payload.get("restore_checkout_commit") or ""),
        "forward_compatible_restore": bool(payload.get("forward_compatible_restore")),
        "postgres_major": payload.get("postgres_major"),
        "restore_started_at": str(started),
        "service_readiness_confirmed_at": str(ready_at),
        "observed_rto_seconds": rto,
        "local_ai_smoke_requested": bool(payload.get("local_ai_smoke_requested")),
    }
    return check(PASS, "restore-observation", "Restore observation is structurally valid.", observed_rto_seconds=rto), sanitized


def sanitize_ai_report(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if payload is None:
        return check(NOT_MEASURED, "ai-adversarial", "Real-model adversarial evaluation was not supplied."), None
    if payload.get("schema") != AI_SCHEMA:
        return check(FAIL, "ai-adversarial", "Unsupported or malformed AI evaluation schema."), None
    real_model = payload.get("real_model") is True
    execution_complete = payload.get("execution_complete") is True
    automatic_ok = payload.get("automatic_checks_ok") is True
    if not real_model:
        status = FAIL
        note = "Mock/non-real model evidence is not valid pilot security evidence."
    elif not execution_complete or not automatic_ok:
        status = FAIL
        note = "Real-model automatic adversarial checks did not pass completely."
    else:
        status = PASS
        note = "Real-model automatic adversarial checks passed; human review is still required."

    sanitized_results = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        sanitized_results.append(
            {
                "case_id": row.get("case_id"),
                "title": row.get("title"),
                "attack_location": row.get("attack_location"),
                "execution_status": row.get("execution_status"),
                "automatic_pass": row.get("automatic_pass") is True,
                "finding_codes": list(row.get("finding_codes") or []),
                "leaked_canary_count": int(row.get("leaked_canary_count") or 0),
                "human_review_status": row.get("human_review_status") or "pending",
            }
        )
    provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    sanitized = {
        "schema": payload.get("schema"),
        "suite_version": payload.get("suite_version"),
        "generated_at": payload.get("generated_at"),
        "provider": {
            "id": provider.get("id"),
            "name": provider.get("name"),
            "provider_type": provider.get("provider_type"),
            "model_name": provider.get("model_name"),
        },
        "real_model": real_model,
        "case_count": payload.get("case_count"),
        "execution_complete": execution_complete,
        "automatic_checks_ok": automatic_ok,
        "human_review_required": payload.get("human_review_required") is True,
        "human_review_status": payload.get("human_review_status") or "pending",
        "results": sanitized_results,
    }
    return check(status, "ai-adversarial", note), sanitized


def valid_manual_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in ALLOWED_MANUAL_STATUS:
        return False
    for key in ("reviewer", "observed_at", "note"):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            return False
    refs = entry.get("evidence_refs", [])
    return isinstance(refs, list) and all(isinstance(item, str) and item.strip() for item in refs)


def manual_checks(payload: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    observations = {}
    if isinstance(payload, dict) and payload.get("schema") == MANUAL_SCHEMA and isinstance(payload.get("observations"), dict):
        observations = payload["observations"]

    checks: dict[str, dict[str, Any]] = {}
    sanitized: dict[str, Any] = {"schema": MANUAL_SCHEMA, "observations": {}}
    for key in MANUAL_KEYS:
        entry = observations.get(key)
        if not valid_manual_entry(entry):
            checks[key] = check(MANUAL_REQUIRED, "operator-attestation", "Valid operator attestation has not been supplied.")
            continue
        clean_entry = {
            "status": entry["status"],
            "reviewer": sanitize_text(entry["reviewer"], 200),
            "observed_at": sanitize_text(entry["observed_at"], 100),
            "note": sanitize_text(entry["note"], 1000),
            "evidence_refs": [sanitize_text(item, 500) for item in entry.get("evidence_refs", [])],
        }
        sanitized["observations"][key] = clean_entry
        checks[key] = check(entry["status"], "operator-attestation", clean_entry["note"], reviewer=clean_entry["reviewer"], observed_at=clean_entry["observed_at"], evidence_refs=clean_entry["evidence_refs"])
    return checks, sanitized if sanitized["observations"] else None


def probe_tls(base_url: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    parsed = urlparse.urlparse(base_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return check(FAIL, "tls-probe", "Pilot base URL must be an https URL with a hostname."), None
    host = parsed.hostname
    port = parsed.port or 443
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=8) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
                tls_meta = {
                    "hostname": host,
                    "port": port,
                    "tls_version": tls.version(),
                    "cipher": tls.cipher()[0] if tls.cipher() else None,
                    "subject": cert.get("subject"),
                    "issuer": cert.get("issuer"),
                    "serialNumber": cert.get("serialNumber"),
                    "notBefore": cert.get("notBefore"),
                    "notAfter": cert.get("notAfter"),
                }
        req = urlrequest.Request(base_url, method="HEAD", headers={"User-Agent": "grc-pilot-acceptance/1"})
        try:
            with urlrequest.urlopen(req, timeout=8, context=context) as response:
                tls_meta["https_status"] = int(response.status)
                tls_meta["final_url"] = response.geturl()
        except urlerror.HTTPError as exc:
            tls_meta["https_status"] = int(exc.code)
            tls_meta["final_url"] = exc.geturl()
        return check(PASS, "tls-probe", "TLS trust and hostname verification succeeded."), tls_meta
    except Exception as exc:  # noqa: BLE001 - evidence collector must record the failure class safely
        return check(FAIL, "tls-probe", f"TLS probe failed: {exc.__class__.__name__}"), None


def build_summary(automated: dict[str, dict[str, Any]], manual: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks = dict(automated)
    checks.update(manual)
    missing = [name for name in ISSUE7_REQUIRED if checks.get(name, {}).get("status") != PASS]
    issue8_external = (
        "ai_adversarial_automatic",
        "ai_human_review",
        "scanner_real_validation",
        "audit_immutable_storage_validation",
        "pentest_completed_or_scheduled",
    )
    issue8_missing = [name for name in issue8_external if checks.get(name, {}).get("status") != PASS]
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "checks": checks,
        "issue7_required_checks": list(ISSUE7_REQUIRED),
        "issue7_missing_or_failed": missing,
        "ready_to_close_issue_7": not missing,
        "issue8_external_checks_tracked_here": list(issue8_external),
        "issue8_external_missing_or_failed": issue8_missing,
        "issue8_external_checks_complete": not issue8_missing,
        "excluded_by_design": list(EXCLUDED_BY_DESIGN),
        "acceptance_boundary": (
            "This bundle records repository/runtime observations and explicit operator attestations. "
            "It is not a substitute for independent penetration testing or named security sign-off."
        ),
    }


def write_human_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "GRC pilot acceptance evidence summary",
        f"Generated: {summary['generated_at']}",
        "",
    ]
    for name in sorted(summary["checks"]):
        item = summary["checks"][name]
        lines.append(f"{name}: {item.get('status')} [{item.get('source')}]")
    lines.extend(
        [
            "",
            f"ready_to_close_issue_7: {str(summary['ready_to_close_issue_7']).lower()}",
            "missing_or_failed: " + (", ".join(summary["issue7_missing_or_failed"]) or "none"),
            "",
            "Do not attach secret-bearing backup directories or .env files to GitHub.",
        ]
    )
    secure_write(path, "\n".join(lines) + "\n")


def self_test() -> None:
    backup_ok, backup_clean = validate_backup_observation(
        {
            "backup_name": "drill-1",
            "started_at": "2026-09-16T00:00:00Z",
            "completed_at": "2026-09-16T00:00:05Z",
            "duration_seconds": 5,
            "contains_secret_bearing_config": True,
            "tls_private_key_included": False,
            "release_consistent_quiesce": True,
        }
    )
    assert backup_ok["status"] == PASS and backup_clean and "config.env" not in backup_clean
    restore_ok, _ = validate_restore_observation(
        {
            "backup_name": "drill-1",
            "restore_started_at": "2026-09-16T00:01:00Z",
            "service_readiness_confirmed_at": "2026-09-16T00:01:30Z",
            "observed_rto_seconds": 30,
        }
    )
    assert restore_ok["status"] == PASS
    mock_ai, _ = sanitize_ai_report(
        {
            "schema": AI_SCHEMA,
            "real_model": False,
            "execution_complete": True,
            "automatic_checks_ok": True,
            "results": [],
        }
    )
    assert mock_ai["status"] == FAIL
    real_ai, sanitized = sanitize_ai_report(
        {
            "schema": AI_SCHEMA,
            "real_model": True,
            "execution_complete": True,
            "automatic_checks_ok": True,
            "human_review_required": True,
            "provider": {"id": "1", "name": "local", "provider_type": "ollama", "model_name": "approved"},
            "results": [
                {
                    "case_id": "case-1",
                    "execution_status": "completed",
                    "automatic_pass": True,
                    "response": "must-not-survive",
                    "system_canary": "must-not-survive",
                }
            ],
        }
    )
    assert real_ai["status"] == PASS
    assert sanitized and "response" not in sanitized["results"][0] and "system_canary" not in sanitized["results"][0]

    invalid_manual, _ = manual_checks({"schema": MANUAL_SCHEMA, "observations": {"clean_host_confirmed": {"status": PASS}}})
    assert invalid_manual["clean_host_confirmed"]["status"] == MANUAL_REQUIRED

    valid_entry = {
        "status": PASS,
        "reviewer": "pilot-operator",
        "observed_at": "2026-09-16T00:02:00Z",
        "note": "Observed on approved pilot host.",
        "evidence_refs": ["ticket:123"],
    }
    manual_payload = {"schema": MANUAL_SCHEMA, "observations": {key: dict(valid_entry) for key in MANUAL_KEYS}}
    manual, _ = manual_checks(manual_payload)
    automated = {name: check(PASS, "self-test") for name in ISSUE7_REQUIRED if name not in MANUAL_KEYS}
    automated["ai_adversarial_automatic"] = real_ai
    summary = build_summary(automated, manual)
    assert summary["ready_to_close_issue_7"] is True

    incomplete = build_summary({"release_commit": check(PASS, "self-test")}, {})
    assert incomplete["ready_to_close_issue_7"] is False
    assert "core_services_healthy" in incomplete["issue7_missing_or_failed"]
    assert "must-not-survive" not in json.dumps(sanitized)
    print("pilot acceptance evidence self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="Output directory. Defaults to artifacts/pilot-acceptance-<UTC timestamp>.")
    parser.add_argument("--env-file", default=".env", help="Compose env file path; contents are never read or copied by this tool.")
    parser.add_argument("--tls", action="store_true", help="Include docker-compose.pilot.tls.yml in Compose commands.")
    parser.add_argument("--base-url", help="Approved HTTPS pilot URL for certificate/trust probing.")
    parser.add_argument("--ai-provider-id", help="AIProviderConfig UUID for real generation + embedding readiness.")
    parser.add_argument("--ai-tenant-code", help="Tenant code for the real-model adversarial evaluator.")
    parser.add_argument("--backup-observation", type=Path, help="Explicit path to backup-observation.json only.")
    parser.add_argument("--restore-observation", type=Path, help="Explicit path to restore-observation.json only.")
    parser.add_argument("--manual-observations", type=Path, help="Operator attestation JSON using grc-pilot-manual-observations-v1.")
    parser.add_argument("--require-complete", action="store_true", help="Exit non-zero unless every Issue #7 required check is PASS.")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic tests without Docker/network and exit.")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else Path("artifacts") / f"pilot-acceptance-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    try:
        os.chmod(out, 0o700)
    except OSError:
        pass

    automated: dict[str, dict[str, Any]] = {}

    code, stdout, _ = run_command(["git", "rev-parse", "HEAD"], timeout=15)
    commit = stdout.strip() if code == 0 else ""
    if code == 0 and HEX40.fullmatch(commit):
        automated["release_commit"] = check(PASS, "git", "Exact release checkout commit recorded.", commit=commit)
        secure_write(out / "release-commit.txt", commit + "\n")
    else:
        automated["release_commit"] = check(FAIL, "git", "Unable to record a valid 40-character release commit.")

    code, stdout, _ = run_command(["git", "status", "--porcelain", "--untracked-files=no"], timeout=15)
    if code == 0:
        clean = not stdout.strip()
        automated["release_checkout_clean"] = check(PASS if clean else FAIL, "git", "Tracked checkout is clean." if clean else "Tracked checkout has local modifications.")
    else:
        automated["release_checkout_clean"] = check(FAIL, "git", "Unable to verify checkout cleanliness.")

    os_meta = collect_os_metadata()
    secure_json(out / "host-os.json", os_meta)
    automated["host_os_metadata"] = check(PASS, "host-os", "Host OS metadata captured; clean-host provenance still requires operator attestation.")

    env_path = Path(args.env_file)
    compose = ["docker", "compose", "--env-file", str(env_path), "-f", "docker-compose.pilot.yml"]
    if args.tls:
        compose += ["-f", "docker-compose.pilot.tls.yml"]

    if not env_path.is_file():
        for name in ("docker_runtime", "compose_service_state", "core_services_healthy", "local_ai_generation_embedding"):
            automated[name] = check(NOT_MEASURED, "runtime", f"Compose execution skipped because {env_path} is absent.")
    else:
        code, stdout, stderr = run_command(["docker", "version"], timeout=30)
        automated["docker_runtime"] = check(status_from_exit(code), "docker", "Docker runtime version collected." if code == 0 else "Docker runtime check failed.")
        if code == 0:
            secure_write(out / "docker-version.txt", sanitize_text(stdout + stderr, 8000))

        code, stdout, stderr = run_command(["docker", "compose", "version"], timeout=30)
        if code == 0:
            secure_write(out / "compose-version.txt", sanitize_text(stdout + stderr, 4000))

        code, stdout, stderr = run_command(compose + ["ps"], timeout=45)
        automated["compose_service_state"] = check(status_from_exit(code), "docker-compose", "Compose service state captured." if code == 0 else "Unable to read Compose service state.")
        if code is not None:
            secure_write(out / "service-state.txt", sanitize_text(stdout + stderr, 12000))

        code, stdout, stderr = run_command(compose + ["config", "--images"], timeout=45)
        if code is not None:
            secure_write(out / "compose-images.txt", sanitize_text(stdout + stderr, 8000))

        readiness = compose + ["exec", "-T", "backend", "python", "manage.py", "pilot_readiness"]
        code, stdout, stderr = run_command(readiness, timeout=120)
        automated["core_services_healthy"] = check(status_from_exit(code, unavailable_is_not_measured=False), "pilot_readiness", "Core pilot readiness passed." if code == 0 else "Core pilot readiness did not pass.")
        secure_write(out / "pilot-readiness.txt", sanitize_text(stdout + stderr, 12000))

        if args.ai_provider_id:
            ai_readiness = readiness + ["--ai-provider-id", args.ai_provider_id]
            code, stdout, stderr = run_command(ai_readiness, timeout=180)
            automated["local_ai_generation_embedding"] = check(status_from_exit(code, unavailable_is_not_measured=False), "pilot_readiness-ai", "Real provider generation + embedding readiness passed." if code == 0 else "AI generation + embedding readiness did not pass.")
            secure_write(out / "pilot-ai-readiness.txt", sanitize_text(stdout + stderr, 12000))
        else:
            automated["local_ai_generation_embedding"] = check(NOT_MEASURED, "pilot_readiness-ai", "No AI provider ID was supplied.")

        if args.ai_tenant_code:
            command = compose + ["exec", "-T", "backend", "python", "manage.py", "evaluate_ai_security", "--tenant-code", args.ai_tenant_code]
            if args.ai_provider_id:
                command += ["--provider-id", args.ai_provider_id]
            code, stdout, stderr = run_command(command, timeout=600)
            try:
                raw_ai = json.loads(stdout) if stdout.strip() else None
            except json.JSONDecodeError:
                raw_ai = None
            ai_check, ai_sanitized = sanitize_ai_report(raw_ai if isinstance(raw_ai, dict) else None)
            if code not in (0, None) and ai_check["status"] == PASS:
                ai_check = check(FAIL, "ai-adversarial", "Evaluator command exited non-zero despite a parseable report.")
            automated["ai_adversarial_automatic"] = ai_check
            if ai_sanitized is not None:
                secure_json(out / "ai-security-summary.json", ai_sanitized)
            if stderr.strip():
                secure_write(out / "ai-security-evaluator.stderr.txt", sanitize_text(stderr, 4000))
        else:
            automated["ai_adversarial_automatic"] = check(NOT_MEASURED, "ai-adversarial", "No tenant code was supplied for real-model adversarial evaluation.")

    if args.base_url:
        tls_check, tls_meta = probe_tls(args.base_url)
        automated["tls_endpoint"] = tls_check
        if tls_meta is not None:
            secure_json(out / "tls-endpoint.json", tls_meta)
    else:
        automated["tls_endpoint"] = check(NOT_MEASURED, "tls-probe", "No approved HTTPS pilot URL was supplied.")

    backup_check, backup_sanitized = validate_backup_observation(load_json(args.backup_observation))
    automated["backup_observation"] = backup_check
    if backup_sanitized is not None:
        secure_json(out / "backup-observation-summary.json", backup_sanitized)

    restore_check, restore_sanitized = validate_restore_observation(load_json(args.restore_observation))
    automated["restore_observation"] = restore_check
    if restore_sanitized is not None:
        secure_json(out / "restore-observation-summary.json", restore_sanitized)

    manual_payload = load_json(args.manual_observations)
    manual, manual_sanitized = manual_checks(manual_payload)
    if manual_sanitized is not None:
        secure_json(out / "manual-observations-summary.json", manual_sanitized)

    summary = build_summary(automated, manual)
    secure_json(out / "acceptance-summary.json", summary)
    write_human_summary(out / "acceptance-summary.txt", summary)
    for child in out.iterdir():
        if child.is_file():
            try:
                os.chmod(child, 0o600)
            except OSError:
                pass

    print(f"Pilot acceptance evidence collected at: {out}")
    print(f"ready_to_close_issue_7={str(summary['ready_to_close_issue_7']).lower()}")
    if summary["issue7_missing_or_failed"]:
        print("Issue #7 still requires: " + ", ".join(summary["issue7_missing_or_failed"]))
    if args.require_complete and not summary["ready_to_close_issue_7"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

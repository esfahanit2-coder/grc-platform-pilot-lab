#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LOG_FIELDS = {
    "timestamp",
    "time",
    "level",
    "logger",
    "request_id",
    "method",
    "path",
    "status",
    "duration",
    "duration_ms",
    "error_type",
}
ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}


def run(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "command-not-found")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return subprocess.CompletedProcess(command, 124, stdout, stderr or "command-timeout")


def safe_json(text: str) -> dict | list | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def compose(env_file: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        "docker-compose.pilot.yml",
        "-f",
        "docker-compose.pilot.tls.yml",
    ]


def sanitize_log_line(raw: str) -> dict | None:
    payload = safe_json(raw)
    if not isinstance(payload, dict):
        return None
    level = str(payload.get("level", "")).upper()
    try:
        status = int(payload.get("status", 0) or 0)
    except (TypeError, ValueError):
        status = 0
    error_type = payload.get("error_type")
    if level not in ERROR_LEVELS and status < 500 and not error_type:
        return None

    result = {}
    for key in ALLOWED_LOG_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                value = value[:240]
            result[key] = value
    return result


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def collect(env_file: Path, output: Path, since_minutes: int) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    version = ""
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("GRC_RELEASE_VERSION="):
            version = raw.split("=", 1)[1].strip().strip("'\"")
            break

    verification_path = output / "verification.json"
    verification = run(
        [
            sys.executable,
            "scripts/datacenter-verify.py",
            "--env",
            str(env_file),
            "--release-version",
            version,
            "--json-out",
            str(verification_path),
        ],
        timeout=180,
    )
    if not verification_path.exists():
        write_json(
            verification_path,
            {
                "schema": "grc-datacenter-verification-v1",
                "ok": False,
                "collector_error_type": "VerificationUnavailable",
            },
        )

    comp = compose(env_file)
    migration = run(comp + ["exec", "-T", "backend", "python", "manage.py", "release_migration_plan"])
    migration_json = safe_json(migration.stdout)
    write_json(
        output / "migration-status.json",
        migration_json
        if isinstance(migration_json, dict)
        else {
            "schema": "grc-support-migration-status-v1",
            "available": False,
            "error_type": "MigrationStatusUnavailable" if migration.returncode else "MigrationStatusInvalid",
        },
    )

    operational = run(comp + ["exec", "-T", "backend", "python", "manage.py", "operational_status", "--json"])
    operational_json = safe_json(operational.stdout)
    write_json(
        output / "operational-status.json",
        operational_json
        if isinstance(operational_json, dict)
        else {
            "schema": "grc-support-operational-status-v1",
            "available": False,
            "error_type": "OperationalStatusUnavailable" if operational.returncode else "OperationalStatusInvalid",
        },
    )

    errors: list[dict] = []
    backend_id = run(comp + ["ps", "-q", "backend"])
    cid = backend_id.stdout.strip()
    if cid:
        logs = run(
            [
                "docker",
                "logs",
                "--since",
                f"{since_minutes}m",
                "--tail",
                "500",
                cid,
            ]
        )
        for raw in (logs.stdout + "\n" + logs.stderr).splitlines():
            item = sanitize_log_line(raw)
            if item:
                errors.append(item)
                if len(errors) >= 100:
                    break
    write_json(
        output / "recent-errors.json",
        {
            "schema": "grc-support-recent-errors-v1",
            "window_minutes": since_minutes,
            "max_entries": 100,
            "entries": errors,
            "raw_logs_persisted": False,
        },
    )

    current_commit = run(["git", "rev-parse", "HEAD"])
    summary = {
        "schema": "grc-datacenter-support-bundle-v1",
        "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "release_version": version or None,
        "source_commit": current_commit.stdout.strip() if current_commit.returncode == 0 else None,
        "verification_exit_code": verification.returncode,
        "included": [
            "secret-safe installation verification",
            "migration status",
            "operational status",
            "bounded allowlisted structured error metadata",
        ],
        "excluded_by_design": [
            "environment file and environment-variable values",
            "TLS certificates and private keys",
            "database dumps",
            "object-store contents and evidence documents",
            "connector and SMTP credentials",
            "raw application/service logs",
            "customer records",
            "AI prompts, responses and knowledge payloads",
        ],
    }
    write_json(output / "bundle-summary.json", summary)

    archive = output.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(output, arcname=output.name, recursive=True)
    os.chmod(archive, 0o600)
    return archive


def self_test() -> None:
    sentinel = "TOP-SECRET-CUSTOMER-VALUE"
    raw = json.dumps(
        {
            "level": "ERROR",
            "request_id": "req-1",
            "path": "/api/v1/example/",
            "status": 500,
            "error_type": "ExampleError",
            "authorization": sentinel,
            "request_body": sentinel,
            "tenant_name": sentinel,
        }
    )
    clean = sanitize_log_line(raw)
    if not clean or clean.get("status") != 500:
        raise SystemExit("support log sanitizer did not keep bounded error metadata")
    encoded = json.dumps(clean)
    if sentinel in encoded or "authorization" in clean or "request_body" in clean or "tenant_name" in clean:
        raise SystemExit("support log sanitizer leaked a forbidden field")
    if sanitize_log_line(json.dumps({"level": "INFO", "status": 200})) is not None:
        raise SystemExit("support log sanitizer retained a non-error line")
    print("datacenter support bundle self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a bounded, secret-safe GRC datacenter support bundle.")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output")
    parser.add_argument("--since-minutes", type=int, default=30)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if args.since_minutes < 1 or args.since_minutes > 1440:
        print("ERROR: --since-minutes must be between 1 and 1440", file=sys.stderr)
        return 2

    env_file = Path(args.env).resolve()
    if not env_file.is_file():
        print("ERROR: environment file is required", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output or ROOT / "artifacts" / f"datacenter-support-{stamp}").resolve()
    try:
        archive = collect(env_file, output, args.since_minutes)
    except FileExistsError:
        print(f"ERROR: output already exists: {output}", file=sys.stderr)
        return 3
    print(json.dumps({"support_directory": str(output), "archive": str(archive)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


PLACEHOLDER_MARKERS = (
    "replace-with-",
    "change-me",
    "changeme",
    "example-password",
    "example-secret",
)
REQUIRED_KEYS = (
    "APP_ENV",
    "GRC_RELEASE_VERSION",
    "DJANGO_SECRET_KEY",
    "AUDIT_INTEGRITY_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "POSTGRES_PASSWORD",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "OPS_METRICS_TOKEN",
    "S3_ENDPOINT_URL",
    "S3_BUCKET",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "MFA_ENCRYPTION_KEY",
    "TLS_CERT_PATH",
    "TLS_KEY_PATH",
)


def parse_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"line {number} is not KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or any(ch.isspace() for ch in key):
            raise ValueError(f"line {number} has an invalid key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def https_origin(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_env_path(env_path: Path, configured: str) -> Path:
    candidate = Path(configured)
    if not candidate.is_absolute():
        candidate = (env_path.parent / candidate).resolve()
    return candidate


def openssl_run(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["openssl", *args],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(["openssl", *args], 127, b"", b"")


def validate(path: Path, expected_release: str | None = None, require_tls_files: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    tls_certificate_valid: bool | None = None
    tls_private_key_valid: bool | None = None
    tls_keypair_match: bool | None = None
    try:
        env = parse_env(path)
    except Exception as exc:
        return {
            "schema": "grc-datacenter-config-validation-v1",
            "valid": False,
            "errors": [f"environment file cannot be parsed: {type(exc).__name__}"],
            "warnings": [],
        }

    try:
        env_mode = stat.S_IMODE(path.stat().st_mode)
        if env_mode & 0o077:
            errors.append("production environment file permissions must not grant group/other access")
    except OSError:
        errors.append("production environment file permissions could not be inspected")

    missing = [key for key in REQUIRED_KEYS if not env.get(key, "").strip()]
    if missing:
        errors.append("required keys missing or empty: " + ", ".join(sorted(missing)))

    if env.get("APP_ENV") != "production":
        errors.append("APP_ENV must be production")
    if truthy(env.get("DJANGO_DEBUG")):
        errors.append("DJANGO_DEBUG must be disabled")
    for key in ("AUTH_COOKIE_MODE", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"):
        if not truthy(env.get(key)):
            errors.append(f"{key} must be enabled")
    if not truthy(env.get("EVIDENCE_REQUIRE_CLEAN_DOWNLOAD")):
        errors.append("EVIDENCE_REQUIRE_CLEAN_DOWNLOAD must be enabled")

    release = env.get("GRC_RELEASE_VERSION", "").strip()
    if release in {"", "local", "latest"} or placeholder(release):
        errors.append("GRC_RELEASE_VERSION must identify an immutable release")
    if expected_release and release != expected_release:
        errors.append("GRC_RELEASE_VERSION does not match the signed/selected release")

    for key, minimum in (
        ("DJANGO_SECRET_KEY", 50),
        ("AUDIT_INTEGRITY_KEY", 32),
        ("POSTGRES_PASSWORD", 16),
        ("OPS_METRICS_TOKEN", 32),
        ("S3_ACCESS_KEY", 12),
        ("S3_SECRET_KEY", 24),
    ):
        value = env.get(key, "")
        if placeholder(value) or len(value) < minimum:
            errors.append(f"{key} is missing, placeholder-like, or shorter than the production minimum")

    mfa_key = env.get("MFA_ENCRYPTION_KEY", "")
    if placeholder(mfa_key):
        errors.append("MFA_ENCRYPTION_KEY must be a dedicated Fernet key")
    else:
        try:
            decoded = base64.urlsafe_b64decode(mfa_key.encode("ascii"))
            if len(decoded) != 32:
                raise ValueError("wrong length")
        except Exception:
            errors.append("MFA_ENCRYPTION_KEY must be a valid 32-byte urlsafe-base64 Fernet key")

    hosts = split_csv(env.get("DJANGO_ALLOWED_HOSTS", ""))
    if not hosts or "*" in hosts:
        errors.append("DJANGO_ALLOWED_HOSTS must be explicit and must not contain *")
    if any(host.endswith(".example.internal") or host == "grc.example.internal" for host in hosts):
        errors.append("DJANGO_ALLOWED_HOSTS still contains the example hostname")

    for key in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        origins = split_csv(env.get(key, ""))
        if not origins or any(not https_origin(origin) for origin in origins):
            errors.append(f"{key} must contain only explicit https origins")

    endpoint = env.get("S3_ENDPOINT_URL", "")
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.hostname:
        errors.append("S3_ENDPOINT_URL must be an explicit http(s) endpoint")
    if truthy(env.get("S3_USE_SSL")) and parsed_endpoint.scheme != "https":
        errors.append("S3_USE_SSL requires an https S3_ENDPOINT_URL")
    if parsed_endpoint.scheme == "http" and parsed_endpoint.hostname not in {"objectstore", "127.0.0.1", "localhost"}:
        warnings.append("S3 endpoint is HTTP outside the bundled private objectstore name; verify network isolation")

    if truthy(env.get("NOTIFICATION_EMAIL_ENABLED")):
        if not env.get("EMAIL_HOST", "").strip():
            errors.append("EMAIL_HOST is required when notification email is enabled")
        if not env.get("DEFAULT_FROM_EMAIL", "").strip() or "@" not in env.get("DEFAULT_FROM_EMAIL", ""):
            errors.append("DEFAULT_FROM_EMAIL must be configured when notification email is enabled")
        if not https_origin(env.get("APP_BASE_URL", "")):
            errors.append("APP_BASE_URL must be an explicit https URL when notification email is enabled")
        if truthy(env.get("EMAIL_USE_TLS")) and truthy(env.get("EMAIL_USE_SSL")):
            errors.append("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled")
        if env.get("EMAIL_HOST_USER", "").strip() and placeholder(env.get("EMAIL_HOST_PASSWORD", "")):
            errors.append("EMAIL_HOST_PASSWORD is required when EMAIL_HOST_USER is configured")

    if require_tls_files:
        cert_path = resolve_env_path(path, env.get("TLS_CERT_PATH", "").strip())
        key_path = resolve_env_path(path, env.get("TLS_KEY_PATH", "").strip())
        if not cert_path.is_file():
            errors.append("TLS_CERT_PATH does not point to an existing file")
        if not key_path.is_file():
            errors.append("TLS_KEY_PATH does not point to an existing file")
        if key_path.is_file():
            mode = stat.S_IMODE(key_path.stat().st_mode)
            if mode & 0o077:
                errors.append("TLS private key permissions must not grant group/other access")

        if cert_path.is_file():
            cert_check = openssl_run("x509", "-in", str(cert_path), "-noout", "-checkend", "0")
            tls_certificate_valid = cert_check.returncode == 0
            if not tls_certificate_valid:
                errors.append("TLS certificate must parse and must not be expired")
        if key_path.is_file():
            key_check = openssl_run("pkey", "-in", str(key_path), "-noout", "-check")
            tls_private_key_valid = key_check.returncode == 0
            if not tls_private_key_valid:
                errors.append("TLS private key must parse successfully")

        if cert_path.is_file() and key_path.is_file() and tls_certificate_valid and tls_private_key_valid:
            cert_pub = openssl_run("x509", "-in", str(cert_path), "-pubkey", "-noout")
            key_pub = openssl_run("pkey", "-in", str(key_path), "-pubout")
            tls_keypair_match = (
                cert_pub.returncode == 0
                and key_pub.returncode == 0
                and cert_pub.stdout == key_pub.stdout
                and bool(cert_pub.stdout)
            )
            if not tls_keypair_match:
                errors.append("TLS certificate public key does not match the configured private key")

    return {
        "schema": "grc-datacenter-config-validation-v1",
        "valid": not errors,
        "release_version": release or None,
        "checks": {
            "production_mode": env.get("APP_ENV") == "production",
            "secure_cookies": all(truthy(env.get(k)) for k in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE")),
            "tls_paths_checked": require_tls_files,
            "tls_certificate_valid": tls_certificate_valid,
            "tls_private_key_valid": tls_private_key_valid,
            "tls_keypair_match": tls_keypair_match,
            "evidence_download_fail_closed": truthy(env.get("EVIDENCE_REQUIRE_CLEAN_DOWNLOAD")),
            "smtp_enabled": truthy(env.get("NOTIFICATION_EMAIL_ENABLED")),
        },
        "errors": errors,
        "warnings": warnings,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fernet = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
        sample = {
            "APP_ENV": "production",
            "GRC_RELEASE_VERSION": "v1.2.3",
            "DJANGO_SECRET_KEY": "s" * 60,
            "AUDIT_INTEGRITY_KEY": "a" * 40,
            "DJANGO_DEBUG": "0",
            "DJANGO_ALLOWED_HOSTS": "grc.customer.internal",
            "CORS_ALLOWED_ORIGINS": "https://grc.customer.internal",
            "CSRF_TRUSTED_ORIGINS": "https://grc.customer.internal",
            "POSTGRES_PASSWORD": "p" * 24,
            "REDIS_URL": "redis://redis:6379/0",
            "CELERY_BROKER_URL": "redis://redis:6379/1",
            "CELERY_RESULT_BACKEND": "redis://redis:6379/2",
            "OPS_METRICS_TOKEN": "m" * 40,
            "S3_ENDPOINT_URL": "http://objectstore:8333",
            "S3_BUCKET": "grc-evidence",
            "S3_ACCESS_KEY": "k" * 16,
            "S3_SECRET_KEY": "z" * 32,
            "S3_USE_SSL": "0",
            "MFA_ENCRYPTION_KEY": fernet,
            "AUTH_COOKIE_MODE": "1",
            "SESSION_COOKIE_SECURE": "1",
            "CSRF_COOKIE_SECURE": "1",
            "SECURE_SSL_REDIRECT": "1",
            "EVIDENCE_REQUIRE_CLEAN_DOWNLOAD": "1",
            "TLS_CERT_PATH": "./server.crt",
            "TLS_KEY_PATH": "./server.key",
            "NOTIFICATION_EMAIL_ENABLED": "0",
        }
        cert_path = root / "server.crt"
        key_path = root / "server.key"
        generated = openssl_run(
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-subj",
            "/CN=grc.customer.internal",
            "-days",
            "1",
        )
        if generated.returncode != 0:
            raise SystemExit("self-test could not generate TLS fixture")
        key_path.chmod(0o600)

        env_file = root / ".env"
        env_file.write_text("\n".join(f"{k}={v}" for k, v in sample.items()) + "\n", encoding="utf-8")
        env_file.chmod(0o600)
        result = validate(env_file, expected_release="v1.2.3", require_tls_files=True)
        if not result["valid"] or not all(
            result["checks"].get(name) is True
            for name in ("tls_certificate_valid", "tls_private_key_valid", "tls_keypair_match")
        ):
            raise SystemExit("self-test valid TLS fixture failed")

        wrong_key = root / "wrong.key"
        wrong = openssl_run(
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(wrong_key),
        )
        if wrong.returncode != 0:
            raise SystemExit("self-test could not generate mismatched key")
        wrong_key.chmod(0o600)
        mismatch_env = env_file.read_text(encoding="utf-8").replace(
            "TLS_KEY_PATH=./server.key", "TLS_KEY_PATH=./wrong.key"
        )
        env_file.write_text(mismatch_env, encoding="utf-8")
        mismatch = validate(env_file, expected_release="v1.2.3", require_tls_files=True)
        if mismatch["valid"] or mismatch["checks"].get("tls_keypair_match") is not False:
            raise SystemExit("self-test TLS keypair mismatch did not fail closed")

        env_file.write_text("\n".join(f"{k}={v}" for k, v in sample.items()) + "\n", encoding="utf-8")
        env_file.write_text(env_file.read_text(encoding="utf-8").replace("s" * 60, "replace-with-secret"), encoding="utf-8")
        result = validate(env_file, expected_release="v1.2.3")
        if result["valid"] or any("replace-with-secret" in item for item in result["errors"]):
            raise SystemExit("self-test placeholder/redaction contract failed")
    print("datacenter env validator self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production datacenter environment without printing secret values.")
    parser.add_argument("--env", default=".env", help="Environment file to validate.")
    parser.add_argument("--release-version", help="Expected immutable release version.")
    parser.add_argument("--require-tls-files", action="store_true", help="Require certificate/key files and safe private-key permissions.")
    parser.add_argument("--json-out", help="Optional machine-readable output path.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    path = Path(args.env).resolve()
    if not path.is_file():
        print("ERROR: environment file does not exist", file=sys.stderr)
        return 2
    result = validate(path, args.release_version, args.require_tls_files)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out:
        target = Path(args.json_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
    print(payload)
    return 0 if result["valid"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

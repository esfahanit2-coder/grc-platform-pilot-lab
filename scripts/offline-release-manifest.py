#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

SCHEMA = "grc-offline-release-manifest-v1"
MANIFEST_NAME = "release-manifest.json"
SIGNATURE_NAME = "release-manifest.sig"
METADATA_FILES = {
    "images": "metadata/images.json",
    "security_evidence": "metadata/security-evidence.json",
    "database_migrations": "metadata/migrations.json",
    "configuration_schema": "metadata/config-schema.json",
    "local_ai_models": "metadata/local-ai-models.json",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BundleError(RuntimeError):
    pass


def canonical_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_files(stage: Path) -> list[Path]:
    rows: list[Path] = []
    for path in sorted(stage.rglob("*")):
        if path.is_symlink():
            raise BundleError(f"symlinks are not allowed in an offline release bundle: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(stage).as_posix()
        if relative in {MANIFEST_NAME, SIGNATURE_NAME}:
            continue
        rows.append(path)
    return rows


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"invalid JSON metadata {path}: {exc}") from exc


def require_metadata(stage: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, relative in METADATA_FILES.items():
        path = stage / relative
        if not path.is_file():
            raise BundleError(f"required bundle metadata is missing: {relative}")
        result[key] = load_json(path)
    return result


def enforce_model_boundary(metadata: object, stage: Path) -> None:
    if not isinstance(metadata, dict):
        raise BundleError("local AI metadata must be a JSON object")
    if metadata.get("distribution_mode") != "reference-only":
        raise BundleError("local AI metadata must use distribution_mode=reference-only")
    if any(path.is_file() for path in stage.glob("models/**/*")):
        raise BundleError("third-party model bytes must not be embedded in the release bundle")
    models = metadata.get("models", [])
    if not isinstance(models, list):
        raise BundleError("local AI models must be a list")
    for model in models:
        if not isinstance(model, dict):
            raise BundleError("each local AI model reference must be an object")
        if "bytes_in_bundle" in model and model["bytes_in_bundle"] is not False:
            raise BundleError("local AI model references must declare bytes_in_bundle=false")


def build_manifest(stage: Path, version: str, source_commit: str) -> dict[str, object]:
    if not version or any(ch.isspace() for ch in version):
        raise BundleError("release version must be non-empty and contain no whitespace")
    source_commit = source_commit.lower()
    if not SHA_RE.fullmatch(source_commit):
        raise BundleError("source commit must be a lowercase 40-character Git SHA")

    metadata = require_metadata(stage)
    enforce_model_boundary(metadata["local_ai_models"], stage)

    files = []
    for path in payload_files(stage):
        relative = path.relative_to(stage).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )

    return {
        "schema": SCHEMA,
        "release_version": version,
        "source_commit": source_commit,
        "payload": files,
        **metadata,
    }


def write_manifest(stage: Path, version: str, source_commit: str) -> None:
    manifest = build_manifest(stage, version, source_commit)
    (stage / MANIFEST_NAME).write_text(canonical_json(manifest), encoding="utf-8")


def verify_manifest(stage: Path) -> dict[str, object]:
    manifest_path = stage / MANIFEST_NAME
    if not manifest_path.is_file():
        raise BundleError(f"{MANIFEST_NAME} is missing")
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise BundleError("unsupported or missing release manifest schema")
    if not isinstance(manifest.get("release_version"), str) or not manifest["release_version"]:
        raise BundleError("release manifest has no release_version")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or not SHA_RE.fullmatch(source_commit):
        raise BundleError("release manifest has an invalid source_commit")

    metadata = require_metadata(stage)
    for key, value in metadata.items():
        if manifest.get(key) != value:
            raise BundleError(f"embedded metadata does not match manifest section: {key}")
    enforce_model_boundary(metadata["local_ai_models"], stage)

    rows = manifest.get("payload")
    if not isinstance(rows, list):
        raise BundleError("release manifest payload must be a list")
    expected: dict[str, tuple[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise BundleError("invalid payload row")
        relative = row.get("path")
        digest = row.get("sha256")
        size = row.get("size")
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not isinstance(size, int)
            or size < 0
        ):
            raise BundleError(f"invalid payload entry: {row}")
        if relative in expected:
            raise BundleError(f"duplicate payload entry: {relative}")
        expected[relative] = (digest, size)

    actual_paths = {path.relative_to(stage).as_posix(): path for path in payload_files(stage)}
    if set(actual_paths) != set(expected):
        missing = sorted(set(expected) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(expected))
        raise BundleError(f"bundle payload set mismatch; missing={missing} extra={extra}")

    for relative, path in actual_paths.items():
        digest, size = expected[relative]
        if path.stat().st_size != size:
            raise BundleError(f"size mismatch: {relative}")
        if sha256_file(path) != digest:
            raise BundleError(f"checksum mismatch: {relative}")

    rebuilt = build_manifest(stage, str(manifest["release_version"]), str(source_commit))
    if rebuilt != manifest:
        raise BundleError("manifest is not canonical for the current bundle contents")
    return manifest


def combined_tree_digest(rows: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(str(row["path"]).encode())
        digest.update(b"\0")
        digest.update(str(row["sha256"]).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def prepare_repo_metadata(repo: Path, stage: Path) -> None:
    metadata_dir = stage / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    migrations = []
    for path in sorted((repo / "backend").glob("apps/*/migrations/*.py")):
        if path.name == "__init__.py" or not path.name[:1].isdigit():
            continue
        migrations.append(
            {
                "path": path.relative_to(repo).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    migration_meta = {
        "schema": "grc-migration-artifact-inventory-v1",
        "file_count": len(migrations),
        "tree_sha256": combined_tree_digest(migrations),
        "files": migrations,
        "runtime_policy": "audit pending plan before migrate; rollback is backup-based",
    }
    (metadata_dir / "migrations.json").write_text(canonical_json(migration_meta), encoding="utf-8")

    env_path = repo / ".env.pilot.example"
    variables = []
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        required = value.startswith("replace-with-")
        sensitive = any(token in name.upper() for token in ("SECRET", "PASSWORD", "TOKEN", "KEY"))
        variables.append({"name": name, "required": required, "sensitive": sensitive})
    config_meta = {
        "schema": "grc-pilot-config-schema-v1",
        "template": ".env.pilot.example",
        "template_sha256": sha256_file(env_path),
        "variables": variables,
        "secrets_embedded_in_bundle": False,
    }
    (metadata_dir / "config-schema.json").write_text(canonical_json(config_meta), encoding="utf-8")

    model_meta = {
        "schema": "grc-local-ai-model-references-v1",
        "distribution_mode": "reference-only",
        "models": [],
        "instructions": "Record operator-approved model name, digest, provenance and license reference separately; model bytes are never bundled by this release process.",
    }
    (metadata_dir / "local-ai-models.json").write_text(canonical_json(model_meta), encoding="utf-8")


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="grc-offline-manifest-") as temp:
        root = Path(temp)
        stage = root / "stage"
        repo = root / "repo"
        (repo / "backend/apps/demo/migrations").mkdir(parents=True)
        (repo / "backend/apps/demo/migrations/0001_initial.py").write_text("# migration\n", encoding="utf-8")
        (repo / ".env.pilot.example").write_text("DJANGO_SECRET_KEY=replace-with-secret\nAI_ENABLED=1\n", encoding="utf-8")
        stage.mkdir()
        prepare_repo_metadata(repo, stage)
        (stage / "metadata/images.json").write_text(canonical_json({"schema": "images-v1", "images": []}), encoding="utf-8")
        (stage / "metadata/security-evidence.json").write_text(canonical_json({"schema": "security-v1", "reports": []}), encoding="utf-8")
        (stage / "payload.txt").write_text("deterministic\n", encoding="utf-8")
        source = "a" * 40
        write_manifest(stage, "v-test", source)
        first = (stage / MANIFEST_NAME).read_bytes()
        verify_manifest(stage)
        write_manifest(stage, "v-test", source)
        if first != (stage / MANIFEST_NAME).read_bytes():
            raise BundleError("manifest output changed for identical inputs")
        (stage / "payload.txt").write_text("tampered\n", encoding="utf-8")
        try:
            verify_manifest(stage)
        except BundleError:
            return
        raise BundleError("tamper self-test did not fail closed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and verify deterministic GRC offline release manifests.")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare-metadata")
    prepare.add_argument("--repo", default=".")
    prepare.add_argument("--stage", required=True)

    build = sub.add_parser("build")
    build.add_argument("--stage", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--source-commit", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--stage", required=True)

    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "prepare-metadata":
            prepare_repo_metadata(Path(args.repo).resolve(), Path(args.stage).resolve())
        elif args.command == "build":
            write_manifest(Path(args.stage).resolve(), args.version, args.source_commit)
        elif args.command == "verify":
            manifest = verify_manifest(Path(args.stage).resolve())
            print(f"verified {manifest['release_version']} {manifest['source_commit']}")
        elif args.command == "self-test":
            self_test()
            print("offline release manifest self-test passed")
        return 0
    except BundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

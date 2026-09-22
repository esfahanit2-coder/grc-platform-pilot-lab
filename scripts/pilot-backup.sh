#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

if [[ ! -f .env ]]; then
  echo "ERROR: .env is required. Copy and harden .env.pilot.example first." >&2
  exit 2
fi

NAME="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
if [[ ! "$NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: backup name may contain only letters, numbers, dot, underscore and dash." >&2
  exit 2
fi

QUIESCE="${BACKUP_QUIESCE:-NO}"
LEAVE_QUIESCED="${BACKUP_LEAVE_QUIESCED:-NO}"
REQUIRE_RUNNING="${BACKUP_REQUIRE_RUNNING:-NO}"
if [[ "$LEAVE_QUIESCED" == "YES" && "$QUIESCE" != "YES" ]]; then
  echo "ERROR: BACKUP_LEAVE_QUIESCED=YES requires BACKUP_QUIESCE=YES." >&2
  exit 2
fi

DEST="$ROOT/backups/$NAME"
if [[ -e "$DEST" ]]; then
  echo "ERROR: backup destination already exists: $DEST" >&2
  exit 2
fi
mkdir -p "$DEST"
chmod 700 "$ROOT/backups" "$DEST" 2>/dev/null || true

COMPOSE=(docker compose --env-file .env -f docker-compose.pilot.yml)
START_EPOCH="$(date +%s)"
START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
QUIESCED_NOW=0
BACKUP_SUCCEEDED=0

record_backup_signal() {
  local level="$1"
  shift
  "${COMPOSE[@]}" --profile ops run --rm ops python manage.py record_operational_signal backup "$level" --source pilot-backup "$@" >/dev/null 2>&1 || true
}

on_exit() {
  status=$?
  trap - EXIT
  if [[ "$status" -ne 0 && "$BACKUP_SUCCEEDED" != "1" ]]; then
    record_backup_signal critical --metadata "backup_name=$NAME" --metadata "outcome=failed"
  fi
  if [[ "$QUIESCED_NOW" == "1" && ( "$LEAVE_QUIESCED" != "YES" || "$BACKUP_SUCCEEDED" != "1" ) ]]; then
    echo "Restarting application services after backup..."
    if [[ "$REQUIRE_RUNNING" == "YES" ]]; then
      "${COMPOSE[@]}" start backend worker beat frontend gateway >/dev/null || true
    else
      "${COMPOSE[@]}" up -d --wait backend worker beat frontend gateway >/dev/null || true
    fi
  fi
  exit "$status"
}
trap on_exit EXIT

echo "[1/6] Checking required services..."
if [[ "$REQUIRE_RUNNING" != "YES" ]]; then
  "${COMPOSE[@]}" up -d postgres redis objectstore backend >/dev/null
fi
READY=0
for _ in $(seq 1 12); do
  if "${COMPOSE[@]}" exec -T backend python manage.py pilot_readiness >/dev/null 2>&1; then
    READY=1
    break
  fi
  if [[ "$REQUIRE_RUNNING" == "YES" ]]; then
    break
  fi
  sleep 5
done
if [[ "$READY" != "1" ]]; then
  echo "ERROR: pilot readiness did not pass before backup." >&2
  if [[ "$REQUIRE_RUNNING" != "YES" ]]; then
    "${COMPOSE[@]}" exec -T backend python manage.py pilot_readiness || true
  fi
  exit 3
fi

if [[ "$QUIESCE" == "YES" ]]; then
  echo "[2/6] Quiescing application writers for a release-consistent backup..."
  "${COMPOSE[@]}" stop gateway frontend worker beat backend >/dev/null
  QUIESCED_NOW=1
else
  echo "[2/6] Online backup mode selected; application writers remain active."
fi

echo "[3/6] Backing up PostgreSQL..."
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DEST/postgres.dump"

if [[ ! -s "$DEST/postgres.dump" ]]; then
  echo "ERROR: PostgreSQL backup is empty." >&2
  exit 3
fi

echo "[4/6] Backing up S3-compatible object storage..."
"${COMPOSE[@]}" --profile ops run --rm ops \
  python manage.py pilot_objectstore_archive export \
  --archive "/backups/$NAME/objectstore.zip"

if [[ ! -s "$DEST/objectstore.zip" ]]; then
  echo "ERROR: object-storage backup is empty." >&2
  exit 3
fi

echo "[5/6] Capturing compatibility, configuration and image metadata..."
install -m 600 .env "$DEST/config.env"
install -m 600 docker-compose.pilot.yml "$DEST/docker-compose.pilot.yml"
if [[ -f docker-compose.pilot.tls.yml ]]; then
  install -m 600 docker-compose.pilot.tls.yml "$DEST/docker-compose.pilot.tls.yml"
fi
"${COMPOSE[@]}" config --images | sort -u > "$DEST/images.txt"

if [[ -n "${BACKUP_SOURCE_COMMIT:-}" ]]; then
  SOURCE_COMMIT="$BACKUP_SOURCE_COMMIT"
  if [[ ! "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]] || ! git cat-file -e "${SOURCE_COMMIT}^{commit}" 2>/dev/null; then
    echo "ERROR: BACKUP_SOURCE_COMMIT must be a known 40-character Git commit." >&2
    exit 3
  fi
else
  SOURCE_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
fi
if [[ ! "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "ERROR: unable to record a verifiable source commit for the backup." >&2
  exit 3
fi
printf '%s\n' "$SOURCE_COMMIT" > "$DEST/source-commit.txt"

PG_VERSION_NUM="$("${COMPOSE[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SHOW server_version_num"' | tr -d '\r[:space:]')"
if [[ ! "$PG_VERSION_NUM" =~ ^[0-9]+$ ]]; then
  echo "ERROR: unable to determine PostgreSQL server_version_num." >&2
  exit 3
fi
PG_MAJOR="$((PG_VERSION_NUM / 10000))"

python - "$DEST/backup-manifest.json" "$NAME" "$START_ISO" "$SOURCE_COMMIT" \
  "${GRC_RELEASE_VERSION:-unknown}" "$PG_VERSION_NUM" "$PG_MAJOR" "$QUIESCE" <<'PY'
import json
import sys
from pathlib import Path

path, name, created_at, source_commit, release_version, pg_version_num, pg_major, quiesced = sys.argv[1:]
payload = {
    "schema": "grc-backup-manifest-v1",
    "backup_name": name,
    "created_at": created_at,
    "source_commit": source_commit,
    "release_version": release_version,
    "postgres": {
        "server_version_num": int(pg_version_num),
        "major": int(pg_major),
        "dump_format": "custom",
    },
    "objectstore_archive_schema": 1,
    "release_consistent_quiesce": quiesced == "YES",
    "components": [
        "postgres.dump",
        "objectstore.zip",
        "config.env",
        "docker-compose.pilot.yml",
        "images.txt",
        "source-commit.txt",
    ],
}
Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

(
  cd "$DEST"
  sha256sum postgres.dump objectstore.zip config.env docker-compose.pilot.yml images.txt source-commit.txt backup-manifest.json > SHA256SUMS
  if [[ -f docker-compose.pilot.tls.yml ]]; then
    sha256sum docker-compose.pilot.tls.yml >> SHA256SUMS
  fi
)

END_EPOCH="$(date +%s)"
END_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DURATION="$((END_EPOCH - START_EPOCH))"
cat > "$DEST/backup-observation.json" <<EOF
{
  "backup_name": "$NAME",
  "started_at": "$START_ISO",
  "completed_at": "$END_ISO",
  "duration_seconds": $DURATION,
  "contains_secret_bearing_config": true,
  "tls_private_key_included": false,
  "release_consistent_quiesce": $([[ "$QUIESCE" == "YES" ]] && echo true || echo false),
  "rpo_observation": null,
  "note": "Measure RPO with a controlled application marker during the restore drill; do not infer it from backup duration."
}
EOF
chmod 600 "$DEST"/*
BACKUP_SUCCEEDED=1
record_backup_signal ok --metadata "backup_name=$NAME" --metadata "duration_seconds=$DURATION" --metadata "release_consistent_quiesce=$QUIESCE" --metadata "outcome=success"

echo "[6/6] Backup complete: $DEST"
if [[ "$QUIESCED_NOW" == "1" && "$LEAVE_QUIESCED" == "YES" ]]; then
  echo "Application services remain quiesced for the approved release transition."
fi
echo "IMPORTANT: this directory contains config secrets. Store it only on approved encrypted backup media."

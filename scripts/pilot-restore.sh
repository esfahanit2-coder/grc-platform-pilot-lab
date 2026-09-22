#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

NAME="${1:-}"
if [[ -z "$NAME" || ! "$NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Usage: CONFIRM_RESTORE=YES $0 <backup-name>" >&2
  exit 2
fi
if [[ "${CONFIRM_RESTORE:-NO}" != "YES" ]]; then
  echo "ERROR: restore is destructive. Set CONFIRM_RESTORE=YES after change approval." >&2
  exit 2
fi

SRC="$ROOT/backups/$NAME"
if [[ ! -d "$SRC" ]]; then
  echo "ERROR: backup directory not found: $SRC" >&2
  exit 2
fi
for required in postgres.dump objectstore.zip config.env backup-manifest.json source-commit.txt SHA256SUMS; do
  if [[ ! -s "$SRC/$required" ]]; then
    echo "ERROR: required backup component is missing or empty: $required" >&2
    exit 3
  fi
done

(
  cd "$SRC"
  sha256sum -c SHA256SUMS
)

read_manifest() {
  python - "$SRC/backup-manifest.json" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
value = payload
for part in sys.argv[2].split("."):
    value = value[part]
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

MANIFEST_SCHEMA="$(read_manifest schema)"
MANIFEST_NAME="$(read_manifest backup_name)"
BACKUP_SOURCE_COMMIT="$(read_manifest source_commit)"
BACKUP_PG_MAJOR="$(read_manifest postgres.major)"
BACKUP_QUIESCED="$(read_manifest release_consistent_quiesce)"

if [[ "$MANIFEST_SCHEMA" != "grc-backup-manifest-v1" ]]; then
  echo "ERROR: unsupported backup manifest schema: $MANIFEST_SCHEMA" >&2
  exit 3
fi
if [[ "$MANIFEST_NAME" != "$NAME" ]]; then
  echo "ERROR: backup manifest name does not match requested backup." >&2
  exit 3
fi
if [[ ! "$BACKUP_SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "ERROR: backup source commit is missing or invalid; refusing an unverifiable restore." >&2
  exit 3
fi
if [[ ! "$BACKUP_PG_MAJOR" =~ ^[0-9]+$ ]]; then
  echo "ERROR: backup PostgreSQL major version is invalid." >&2
  exit 3
fi

CURRENT_SOURCE_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
FORWARD_COMPATIBLE_RESTORE=0
if [[ "$CURRENT_SOURCE_COMMIT" != "$BACKUP_SOURCE_COMMIT" ]]; then
  if [[ "${RESTORE_ALLOW_FORWARD_COMPATIBLE:-NO}" != "YES" ]]; then
    echo "ERROR: backup was created at $BACKUP_SOURCE_COMMIT but checkout is $CURRENT_SOURCE_COMMIT." >&2
    echo "Check out the backup source commit for rollback, or explicitly use RESTORE_ALLOW_FORWARD_COMPATIBLE=YES for an ancestor-to-current recovery." >&2
    exit 4
  fi
  if [[ "$BACKUP_QUIESCED" != "true" ]]; then
    echo "ERROR: cross-version restore requires a release-consistent quiesced backup." >&2
    exit 4
  fi
  if ! git cat-file -e "${BACKUP_SOURCE_COMMIT}^{commit}" 2>/dev/null || \
     ! git merge-base --is-ancestor "$BACKUP_SOURCE_COMMIT" "$CURRENT_SOURCE_COMMIT"; then
    echo "ERROR: backup source is not a known ancestor of the current checkout; refusing cross-version restore." >&2
    exit 4
  fi
  FORWARD_COMPATIBLE_RESTORE=1
fi

if [[ "${RESTORE_CONFIG:-NO}" == "YES" ]]; then
  if [[ -f .env ]]; then
    install -m 600 .env ".env.pre-restore.$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  install -m 600 "$SRC/config.env" .env
  echo "Restored .env from backup. Review host-specific values before exposing the service."
elif [[ ! -f .env ]]; then
  echo "ERROR: .env is absent. Either create it or set RESTORE_CONFIG=YES." >&2
  exit 2
fi

COMPOSE=(docker compose --env-file .env -f docker-compose.pilot.yml)
if [[ "${PILOT_TLS:-NO}" == "YES" ]]; then
  COMPOSE+=(-f docker-compose.pilot.tls.yml)
fi
LOCAL_AI=0
if [[ "${PILOT_LOCAL_AI:-NO}" == "YES" ]]; then
  COMPOSE+=(--profile local-ai)
  LOCAL_AI=1
fi

START_EPOCH="$(date +%s)"
START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "[1/8] Stopping application writers..."
"${COMPOSE[@]}" stop gateway frontend worker beat backend >/dev/null 2>&1 || true

echo "[2/8] Starting restore dependencies..."
"${COMPOSE[@]}" up -d postgres redis objectstore >/dev/null

TARGET_PG_VERSION_NUM="$("${COMPOSE[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SHOW server_version_num"' | tr -d '\r[:space:]')"
if [[ ! "$TARGET_PG_VERSION_NUM" =~ ^[0-9]+$ ]]; then
  echo "ERROR: unable to determine target PostgreSQL version." >&2
  exit 3
fi
TARGET_PG_MAJOR="$((TARGET_PG_VERSION_NUM / 10000))"
if [[ "$TARGET_PG_MAJOR" != "$BACKUP_PG_MAJOR" ]]; then
  echo "ERROR: backup PostgreSQL major=$BACKUP_PG_MAJOR, target major=$TARGET_PG_MAJOR. Use an approved PostgreSQL major-upgrade procedure instead." >&2
  exit 4
fi

echo "[3/8] Restoring PostgreSQL..."
cat "$SRC/postgres.dump" | "${COMPOSE[@]}" exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges'

echo "[4/8] Auditing pending migrations before application startup..."
"${COMPOSE[@]}" --profile ops run --rm \
  --user "$(id -u):$(id -g)" \
  ops python manage.py release_migration_plan --require-reversible \
  --json-out "/backups/$NAME/restore-migration-plan.json"

echo "[5/8] Applying audited forward migrations..."
"${COMPOSE[@]}" --profile ops run --rm ops python manage.py migrate --noinput

echo "[6/8] Restoring object storage..."
"${COMPOSE[@]}" --profile ops run --rm ops \
  python manage.py pilot_objectstore_archive restore \
  --archive "/backups/$NAME/objectstore.zip" \
  --replace

echo "[7/8] Starting application services and waiting for health..."
APP_SERVICES=(backend worker beat frontend gateway)
if [[ "$LOCAL_AI" == "1" ]]; then
  APP_SERVICES+=(ollama)
fi
"${COMPOSE[@]}" up -d --wait "${APP_SERVICES[@]}"

READINESS=(python manage.py pilot_readiness)
if [[ -n "${AI_PROVIDER_ID:-}" ]]; then
  READINESS+=(--ai-provider-id "$AI_PROVIDER_ID")
fi
"${COMPOSE[@]}" exec -T backend "${READINESS[@]}"

END_EPOCH="$(date +%s)"
END_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DURATION="$((END_EPOCH - START_EPOCH))"
cat > "$SRC/restore-observation.json" <<EOF
{
  "backup_name": "$NAME",
  "backup_source_commit": "$BACKUP_SOURCE_COMMIT",
  "restore_checkout_commit": "$CURRENT_SOURCE_COMMIT",
  "forward_compatible_restore": $([[ "$FORWARD_COMPATIBLE_RESTORE" == "1" ]] && echo true || echo false),
  "postgres_major": $TARGET_PG_MAJOR,
  "restore_started_at": "$START_ISO",
  "service_readiness_confirmed_at": "$END_ISO",
  "observed_rto_seconds": $DURATION,
  "rpo_observation": null,
  "config_restored": "${RESTORE_CONFIG:-NO}",
  "local_ai_smoke_requested": $([[ -n "${AI_PROVIDER_ID:-}" ]] && echo true || echo false),
  "note": "Record RPO from a controlled application marker created before backup and checked after restore."
}
EOF
chmod 600 "$SRC/restore-observation.json" "$SRC/restore-migration-plan.json"

echo "[8/8] Restore completed and core readiness passed in ${DURATION}s."
echo "Next: verify a controlled application marker, evidence object download, login/CSRF flow, and any local-AI model response required by the drill."

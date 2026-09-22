#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

FROM_REF="${1:-}"
BACKUP_NAME="${2:-pre-upgrade-$(date -u +%Y%m%dT%H%M%SZ)}"
OFFLINE_MODE="${PILOT_OFFLINE:-NO}"
FROM_RELEASE_VERSION="${FROM_RELEASE_VERSION:-$FROM_REF}"
if [[ -z "$FROM_REF" ]]; then
  echo "Usage: CONFIRM_UPGRADE=YES $0 <currently-deployed-ref> [backup-name]" >&2
  exit 2
fi
if [[ "${CONFIRM_UPGRADE:-NO}" != "YES" ]]; then
  echo "ERROR: set CONFIRM_UPGRADE=YES only after the maintenance window and rollback owner are approved." >&2
  exit 2
fi
if [[ ! -f .env ]]; then
  echo "ERROR: .env is required." >&2
  exit 2
fi
if [[ ! "$BACKUP_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: backup name may contain only letters, numbers, dot, underscore and dash." >&2
  exit 2
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: tracked working-tree changes are not allowed during a release transition." >&2
  exit 2
fi
if [[ "$OFFLINE_MODE" != "NO" && "$OFFLINE_MODE" != "YES" ]]; then
  echo "ERROR: PILOT_OFFLINE must be YES or NO." >&2
  exit 2
fi
if [[ "$OFFLINE_MODE" == "YES" ]]; then
  if [[ -z "${GRC_RELEASE_VERSION:-}" || ! "$GRC_RELEASE_VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "ERROR: offline upgrade requires a verified GRC_RELEASE_VERSION image tag." >&2
    exit 2
  fi
fi

FROM_SHA="$(git rev-parse "${FROM_REF}^{commit}" 2>/dev/null || true)"
TARGET_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ ! "$FROM_SHA" =~ ^[0-9a-f]{40}$ || ! "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: both deployed and target releases must resolve to Git commits." >&2
  exit 2
fi
if [[ "$FROM_SHA" == "$TARGET_SHA" ]]; then
  echo "ERROR: deployed and target commits are identical; there is nothing to upgrade." >&2
  exit 2
fi
if ! git merge-base --is-ancestor "$FROM_SHA" "$TARGET_SHA"; then
  echo "ERROR: deployed ref $FROM_SHA is not an ancestor of target $TARGET_SHA." >&2
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

"${COMPOSE[@]}" config >/dev/null
if ! "${COMPOSE[@]}" exec -T backend python manage.py pilot_readiness >/dev/null; then
  echo "ERROR: currently deployed backend is not ready; do not begin an upgrade." >&2
  exit 3
fi

POSTGRES_CONTAINER="$("${COMPOSE[@]}" ps -q postgres)"
if [[ -z "$POSTGRES_CONTAINER" ]]; then
  echo "ERROR: running PostgreSQL container was not found." >&2
  exit 3
fi
NETWORK="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$POSTGRES_CONTAINER" | head -n 1)"
if [[ -z "$NETWORK" ]]; then
  echo "ERROR: unable to determine the pilot Docker network." >&2
  exit 3
fi

PREFLIGHT_BACKEND="grc-upgrade-preflight-backend:${TARGET_SHA:0:12}"
PREFLIGHT_FRONTEND="grc-upgrade-preflight-frontend:${TARGET_SHA:0:12}"
REMOVE_PREFLIGHT_IMAGES=1
if [[ "$OFFLINE_MODE" == "YES" ]]; then
  PREFLIGHT_BACKEND="grc-backend:$GRC_RELEASE_VERSION"
  PREFLIGHT_FRONTEND="grc-frontend:$GRC_RELEASE_VERSION"
  REMOVE_PREFLIGHT_IMAGES=0
fi
QUIESCED=0
PHASE="pre_backup"
START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

on_exit() {
  status=$?
  trap - EXIT
  if [[ "$REMOVE_PREFLIGHT_IMAGES" == "1" ]]; then
    docker image rm -f "$PREFLIGHT_BACKEND" "$PREFLIGHT_FRONTEND" >/dev/null 2>&1 || true
  fi
  if [[ "$status" != "0" && "$QUIESCED" == "1" ]]; then
    if [[ "$PHASE" == "pre_migration" ]]; then
      echo "Upgrade failed before schema migration; restarting the existing release containers." >&2
      "${COMPOSE[@]}" start backend worker beat frontend gateway >/dev/null 2>&1 || true
    else
      echo "Upgrade failed after schema migration began. Application writers are being stopped; use the backup-based rollback path." >&2
      "${COMPOSE[@]}" stop gateway frontend worker beat backend >/dev/null 2>&1 || true
      echo "Rollback: CONFIRM_ROLLBACK=YES bash scripts/pilot-rollback.sh $BACKUP_NAME" >&2
      echo "The rollback helper validates the backup, switches to $FROM_SHA, and invokes that release's restore implementation." >&2
    fi
  fi
  exit "$status"
}
trap on_exit EXIT

if [[ "$OFFLINE_MODE" == "YES" ]]; then
  echo "[1/8] Validating preloaded target images without build or pull..."
  REQUIRED_IMAGES=(
    "$PREFLIGHT_BACKEND"
    "$PREFLIGHT_FRONTEND"
    "pgvector/pgvector:0.8.6-pg18-trixie"
    "redis:8.2.1-alpine"
    "chrislusf/seaweedfs:4.47"
    "nginx:1.28.0-alpine"
  )
  if [[ "$LOCAL_AI" == "1" ]]; then
    REQUIRED_IMAGES+=("ollama/ollama:0.34.1")
  fi
  for image in "${REQUIRED_IMAGES[@]}"; do
    docker image inspect "$image" >/dev/null || {
      echo "ERROR: required offline image is not preloaded: $image" >&2
      exit 3
    }
  done
else
  echo "[1/8] Building target images without replacing running release images..."
  docker build -t "$PREFLIGHT_BACKEND" backend >/dev/null
  docker build -t "$PREFLIGHT_FRONTEND" frontend >/dev/null
fi

echo "[2/8] Auditing target migration plan against the live schema (read-only)..."
docker run --rm --network "$NETWORK" --env-file .env \
  -e POSTGRES_HOST=postgres \
  "$PREFLIGHT_BACKEND" \
  python manage.py release_migration_plan --require-reversible >/dev/null

echo "[3/8] Creating release-consistent rollback backup and quiescing writers..."
BACKUP_SOURCE_COMMIT="$FROM_SHA" \
GRC_RELEASE_VERSION="$FROM_RELEASE_VERSION" \
BACKUP_REQUIRE_RUNNING=YES \
BACKUP_QUIESCE=YES \
BACKUP_LEAVE_QUIESCED=YES \
  bash scripts/pilot-backup.sh "$BACKUP_NAME"
QUIESCED=1
PHASE="pre_migration"

if [[ "$OFFLINE_MODE" == "YES" ]]; then
  echo "[4/8] Offline mode: using verified preloaded Compose images; build is disabled."
else
  echo "[4/8] Building Compose service images from the target checkout..."
  "${COMPOSE[@]}" build backend worker beat ops frontend >/dev/null
fi

echo "[5/8] Re-running migration safety audit with the exact target service image..."
"${COMPOSE[@]}" --profile ops run --rm --no-deps ops \
  python manage.py release_migration_plan --require-reversible \
  --json-out "/backups/$BACKUP_NAME/upgrade-migration-plan.json" >/dev/null

PHASE="migration_started"
echo "[6/8] Applying audited migrations while application writers remain stopped..."
"${COMPOSE[@]}" --profile ops run --rm --no-deps ops python manage.py migrate --noinput

PHASE="target_start"
echo "[7/8] Starting target release and waiting for readiness..."
APP_SERVICES=(postgres redis objectstore backend worker beat frontend gateway)
if [[ "$LOCAL_AI" == "1" ]]; then
  APP_SERVICES+=(ollama)
fi
if [[ "$OFFLINE_MODE" == "YES" ]]; then
  "${COMPOSE[@]}" up -d --no-build --wait "${APP_SERVICES[@]}"
else
  "${COMPOSE[@]}" up -d --wait "${APP_SERVICES[@]}"
fi
"${COMPOSE[@]}" exec -T backend python manage.py pilot_readiness

END_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - "$ROOT/backups/$BACKUP_NAME/upgrade-observation.json" \
  "$FROM_SHA" "$TARGET_SHA" "$BACKUP_NAME" "$START_ISO" "$END_ISO" "$FROM_RELEASE_VERSION" "${GRC_RELEASE_VERSION:-unknown}" "$OFFLINE_MODE" <<'PY'
import json
import sys
from pathlib import Path

path, source, target, backup, started, completed, from_version, to_version, offline_mode = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "schema": "grc-upgrade-observation-v1",
            "from_commit": source,
            "to_commit": target,
            "from_release_version": from_version,
            "to_release_version": to_version,
            "offline_mode": offline_mode == "YES",
            "rollback_backup": backup,
            "started_at": started,
            "completed_at": completed,
            "readiness_passed": True,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
chmod 600 "$ROOT/backups/$BACKUP_NAME/upgrade-observation.json" "$ROOT/backups/$BACKUP_NAME/upgrade-migration-plan.json"
PHASE="complete"

echo "[8/8] Upgrade completed: $FROM_SHA -> $TARGET_SHA"
echo "Rollback backup retained at backups/$BACKUP_NAME. Do not delete it until the release observation window is closed."

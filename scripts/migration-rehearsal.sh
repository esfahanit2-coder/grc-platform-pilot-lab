#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

FROM_REF="${1:-}"
if [[ -z "$FROM_REF" ]]; then
  echo "Usage: $0 <previous-known-release-ref>" >&2
  exit 2
fi

FROM_SHA="$(git rev-parse "${FROM_REF}^{commit}" 2>/dev/null || true)"
TARGET_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ ! "$FROM_SHA" =~ ^[0-9a-f]{40}$ || ! "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: baseline and target must resolve to local Git commits." >&2
  exit 2
fi
if [[ "$FROM_SHA" == "$TARGET_SHA" ]]; then
  echo "ERROR: baseline and target commits are identical." >&2
  exit 2
fi
if ! git merge-base --is-ancestor "$FROM_SHA" "$TARGET_SHA"; then
  echo "ERROR: baseline $FROM_SHA is not an ancestor of target $TARGET_SHA." >&2
  exit 2
fi

RUN_ID="grc-migration-rehearsal-$$-$(date +%s)"
NETWORK="${RUN_ID}-net"
POSTGRES_CONTAINER="${RUN_ID}-postgres"
BASE_IMAGE="${RUN_ID}-base"
TARGET_IMAGE="${RUN_ID}-target"
TMP="$(mktemp -d)"
BASE_WORKTREE="$TMP/base"
REPORT_DIR="${MIGRATION_REHEARSAL_REPORT_DIR:-$ROOT/backups/rehearsals/$RUN_ID}"
mkdir -p "$REPORT_DIR"
chmod 700 "$REPORT_DIR" 2>/dev/null || true
START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cleanup() {
  status=$?
  trap - EXIT
  docker rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  docker image rm -f "$BASE_IMAGE" "$TARGET_IMAGE" >/dev/null 2>&1 || true
  if [[ -d "$BASE_WORKTREE" ]]; then
    git worktree remove --force "$BASE_WORKTREE" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
  exit "$status"
}
trap cleanup EXIT

echo "[1/7] Preparing baseline source worktree..."
git worktree add --detach "$BASE_WORKTREE" "$FROM_SHA" >/dev/null

echo "[2/7] Starting disposable PostgreSQL 18 + pgvector..."
docker network create "$NETWORK" >/dev/null
docker run -d --name "$POSTGRES_CONTAINER" --network "$NETWORK" \
  -e POSTGRES_DB=grc_rehearsal \
  -e POSTGRES_USER=grc \
  -e POSTGRES_PASSWORD=grc-rehearsal-only \
  pgvector/pgvector:0.8.6-pg18-trixie >/dev/null

READY=0
for _ in $(seq 1 30); do
  if docker exec "$POSTGRES_CONTAINER" pg_isready -U grc -d grc_rehearsal >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done
if [[ "$READY" != "1" ]]; then
  echo "ERROR: disposable PostgreSQL did not become ready." >&2
  exit 3
fi

echo "[3/7] Building baseline and target backend images..."
docker build -t "$BASE_IMAGE" "$BASE_WORKTREE/backend" >/dev/null
docker build -t "$TARGET_IMAGE" "$ROOT/backend" >/dev/null

CONTAINER_ENV=(
  --rm
  --network "$NETWORK"
  -e APP_ENV=test
  -e DJANGO_SECRET_KEY=grc-rehearsal-secret-key-at-least-32-bytes
  -e POSTGRES_DB=grc_rehearsal
  -e POSTGRES_USER=grc
  -e POSTGRES_PASSWORD=grc-rehearsal-only
  -e POSTGRES_HOST="$POSTGRES_CONTAINER"
  -e POSTGRES_PORT=5432
)

echo "[4/7] Materializing the previous known release schema..."
docker run "${CONTAINER_ENV[@]}" "$BASE_IMAGE" python manage.py migrate --noinput

echo "[5/7] Auditing target delta before applying it..."
docker run "${CONTAINER_ENV[@]}" "$TARGET_IMAGE" \
  python manage.py release_migration_plan --require-reversible | tee "$REPORT_DIR/migration-plan-before.json" >/dev/null

echo "[6/7] Applying target migrations and validating the final state..."
docker run "${CONTAINER_ENV[@]}" "$TARGET_IMAGE" python manage.py migrate --noinput
docker run "${CONTAINER_ENV[@]}" "$TARGET_IMAGE" \
  python manage.py release_migration_plan --require-reversible | tee "$REPORT_DIR/migration-plan-after.json" >/dev/null
docker run "${CONTAINER_ENV[@]}" "$TARGET_IMAGE" python manage.py check >/dev/null

END_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - "$REPORT_DIR/rehearsal-observation.json" "$FROM_SHA" "$TARGET_SHA" "$START_ISO" "$END_ISO" <<'PY'
import json
import sys
from pathlib import Path

path, source, target, started, completed = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "schema": "grc-migration-rehearsal-v1",
            "from_commit": source,
            "to_commit": target,
            "postgres_major": 18,
            "started_at": started,
            "completed_at": completed,
            "forward_migration_passed": True,
            "post_migration_check_passed": True,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
chmod 600 "$REPORT_DIR"/*.json

echo "[7/7] Migration rehearsal passed: $FROM_SHA -> $TARGET_SHA"
echo "Report: $REPORT_DIR/rehearsal-observation.json"

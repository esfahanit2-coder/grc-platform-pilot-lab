#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

OUT="${1:-artifacts/support-evidence-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"
chmod 700 "$OUT"

COMPOSE=(docker compose --env-file .env -f docker-compose.pilot.yml)
if [[ "${PILOT_TLS:-NO}" == "YES" ]]; then
  COMPOSE+=(-f docker-compose.pilot.tls.yml)
fi

safe_run() {
  local file="$1"
  shift
  if "$@" > "$OUT/$file" 2>&1; then
    printf 'success\n' > "$OUT/$file.status"
  else
    printf 'failed\n' > "$OUT/$file.status"
  fi
}

safe_run docker-version.txt docker version
safe_run compose-version.txt docker compose version
safe_run disk-usage.txt df -h
safe_run service-state.txt "${COMPOSE[@]}" ps
safe_run compose-images.txt "${COMPOSE[@]}" config --images

if BACKEND_ID="$("${COMPOSE[@]}" ps -q backend 2>/dev/null)" && [[ -n "$BACKEND_ID" ]]; then
  if "${COMPOSE[@]}" exec -T backend python manage.py pilot_readiness >/dev/null 2>&1; then
    printf 'pass\n' > "$OUT/pilot-readiness.status"
  else
    printf 'fail\n' > "$OUT/pilot-readiness.status"
  fi
  safe_run operational-status.json "${COMPOSE[@]}" exec -T backend python manage.py operational_status --json
else
  printf 'not-running\n' > "$OUT/pilot-readiness.status"
  printf 'not-running\n' > "$OUT/operational-status.json.status"
fi

python - "$OUT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(sys.argv[1])
statuses = {}
for path in sorted(root.glob("*.status")):
    statuses[path.name] = path.read_text(encoding="utf-8").strip()
payload = {
    "schema": "grc-support-evidence-v1",
    "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "statuses": statuses,
    "excluded_by_design": [
        ".env and environment-variable values",
        "TLS private keys and certificates",
        "database dumps and object-store contents",
        "connector credentials/tokens",
        "application/service logs",
        "customer records, evidence payloads and AI prompts/responses",
    ],
}
(root / "evidence-summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 600 "$OUT"/*

echo "Support evidence collected at: $OUT"
echo "Service logs are excluded by default. If support requests logs, review and redact them locally before transfer."

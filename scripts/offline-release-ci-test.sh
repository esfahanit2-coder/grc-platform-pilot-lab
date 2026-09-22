#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
STAGE="$TMP/v-ci"
mkdir -p "$STAGE/metadata" "$STAGE/payload"

python scripts/offline-release-manifest.py prepare-metadata --repo "$ROOT" --stage "$STAGE"
python - "$STAGE" <<'PY'
import json
import sys
from pathlib import Path
stage = Path(sys.argv[1])
(stage / "metadata/images.json").write_text(
    json.dumps({"schema": "grc-offline-images-v1", "images": []}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
(stage / "metadata/security-evidence.json").write_text(
    json.dumps({"schema": "grc-release-security-evidence-v1", "reports": []}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
(stage / "payload/probe.txt").write_text("offline-release-ci\n", encoding="utf-8")
PY

SOURCE_SHA="$(git rev-parse HEAD)"
python scripts/offline-release-manifest.py build --stage "$STAGE" --version v-ci --source-commit "$SOURCE_SHA"
python scripts/offline-release-manifest.py verify --stage "$STAGE" >/dev/null

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$TMP/private.pem" >/dev/null 2>&1
openssl pkey -in "$TMP/private.pem" -pubout -out "$TMP/public.pem" >/dev/null 2>&1
bash scripts/offline-release-sign.sh "$STAGE" "$TMP/private.pem" "$TMP/v-ci-offline-signed.tar.gz" >/dev/null
bash scripts/offline-release-verify.sh "$TMP/v-ci-offline-signed.tar.gz" "$TMP/public.pem" >/dev/null

printf 'tampered\n' > "$STAGE/payload/probe.txt"
if bash scripts/offline-release-verify.sh "$STAGE" "$TMP/public.pem" >/dev/null 2>&1; then
  echo "ERROR: tampered bundle unexpectedly verified." >&2
  exit 1
fi

echo "offline release signature/checksum/tamper self-test passed"

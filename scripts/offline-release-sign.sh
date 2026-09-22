#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

STAGE="${1:-}"
PRIVATE_KEY="${2:-}"
OUTPUT="${3:-}"
if [[ -z "$STAGE" || -z "$PRIVATE_KEY" ]]; then
  echo "Usage: $0 <prepared-stage-directory> <private-signing-key.pem> [signed-bundle.tar.gz]" >&2
  exit 2
fi
for command in openssl python tar gzip realpath; do
  command -v "$command" >/dev/null || { echo "ERROR: required command not found: $command" >&2; exit 2; }
done
STAGE="$(realpath "$STAGE")"
PRIVATE_KEY="$(realpath "$PRIVATE_KEY")"
if [[ ! -d "$STAGE" || ! -s "$STAGE/release-manifest.json" ]]; then
  echo "ERROR: prepared stage or release-manifest.json not found." >&2
  exit 2
fi
if [[ ! -s "$PRIVATE_KEY" ]]; then
  echo "ERROR: signing key not found." >&2
  exit 2
fi
case "$PRIVATE_KEY" in
  "$ROOT"/*)
    echo "ERROR: private release signing keys must never be stored inside the repository." >&2
    exit 3
    ;;
esac

python scripts/offline-release-manifest.py verify --stage "$STAGE" >/dev/null
VERSION="$(python - "$STAGE/release-manifest.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["release_version"])
PY
)"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$(dirname "$STAGE")/${VERSION}-offline-signed.tar.gz"
fi
OUTPUT="$(realpath -m "$OUTPUT")"
if [[ "$OUTPUT" == "$STAGE"/* ]]; then
  echo "ERROR: signed archive must be outside the staged payload directory." >&2
  exit 3
fi
if [[ -e "$OUTPUT" ]]; then
  echo "ERROR: output already exists: $OUTPUT" >&2
  exit 3
fi

TMP_PUBLIC="$(mktemp)"
cleanup() { rm -f "$TMP_PUBLIC"; }
trap cleanup EXIT

openssl pkey -in "$PRIVATE_KEY" -pubout -out "$TMP_PUBLIC" >/dev/null 2>&1
openssl dgst -sha256 -sign "$PRIVATE_KEY" -out "$STAGE/release-manifest.sig" "$STAGE/release-manifest.json"
openssl dgst -sha256 -verify "$TMP_PUBLIC" -signature "$STAGE/release-manifest.sig" "$STAGE/release-manifest.json" >/dev/null
chmod 600 "$STAGE/release-manifest.sig"

mkdir -p "$(dirname "$OUTPUT")"
(
  cd "$(dirname "$STAGE")"
  tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner -cf - "$(basename "$STAGE")" | gzip -n > "$OUTPUT"
)
chmod 600 "$OUTPUT"
printf '%s  %s\n' "$(sha256sum "$OUTPUT" | awk '{print $1}')" "$(basename "$OUTPUT")" > "$OUTPUT.sha256"
chmod 600 "$OUTPUT.sha256"

echo "Signed offline release bundle created: $OUTPUT"
echo "Trust boundary: distribute the approved public key/fingerprint to operators through a channel separate from the bundle."

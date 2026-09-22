#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

INPUT="${1:-}"
TRUSTED_PUBLIC_KEY="${2:-}"
if [[ -z "$INPUT" || -z "$TRUSTED_PUBLIC_KEY" ]]; then
  echo "Usage: $0 <bundle-directory|signed-bundle.tar.gz> <trusted-public-key.pem>" >&2
  exit 2
fi
for command in openssl python tar realpath; do
  command -v "$command" >/dev/null || { echo "ERROR: required command not found: $command" >&2; exit 2; }
done
INPUT="$(realpath "$INPUT")"
TRUSTED_PUBLIC_KEY="$(realpath "$TRUSTED_PUBLIC_KEY")"
if [[ ! -s "$TRUSTED_PUBLIC_KEY" ]]; then
  echo "ERROR: trusted public key not found." >&2
  exit 2
fi

TMP=""
cleanup() { [[ -n "$TMP" ]] && rm -rf "$TMP"; }
trap cleanup EXIT

if [[ -d "$INPUT" ]]; then
  STAGE="$INPUT"
elif [[ -f "$INPUT" ]]; then
  TMP="$(mktemp -d)"
  python - "$INPUT" "$TMP" <<'PY'
import sys
import tarfile
from pathlib import Path
archive = Path(sys.argv[1])
dest = Path(sys.argv[2]).resolve()
with tarfile.open(archive, "r:gz") as tf:
    members = tf.getmembers()
    if not members:
        raise SystemExit("ERROR: bundle archive is empty")
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise SystemExit(f"ERROR: unsafe archive member: {member.name}")
    tf.extractall(dest, members=members, filter="data")
roots = [p for p in dest.iterdir() if p.is_dir()]
if len(roots) != 1:
    raise SystemExit("ERROR: signed bundle archive must contain exactly one top-level directory")
print(roots[0])
PY
  STAGE="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d -print -quit)"
else
  echo "ERROR: bundle input not found: $INPUT" >&2
  exit 2
fi

for required in release-manifest.json release-manifest.sig; do
  if [[ ! -s "$STAGE/$required" ]]; then
    echo "ERROR: signed bundle is missing $required" >&2
    exit 3
  fi
done

openssl dgst -sha256 \
  -verify "$TRUSTED_PUBLIC_KEY" \
  -signature "$STAGE/release-manifest.sig" \
  "$STAGE/release-manifest.json" >/dev/null || {
    echo "ERROR: release manifest signature verification failed." >&2
    exit 4
  }
python scripts/offline-release-manifest.py verify --stage "$STAGE"

echo "Signature and all manifest checks passed."
echo "Verified stage: $STAGE"

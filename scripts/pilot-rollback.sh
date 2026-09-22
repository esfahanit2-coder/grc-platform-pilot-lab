#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
umask 077

NAME="${1:-}"
if [[ -z "$NAME" || ! "$NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Usage: CONFIRM_ROLLBACK=YES $0 <pre-upgrade-backup-name>" >&2
  exit 2
fi
if [[ "${CONFIRM_ROLLBACK:-NO}" != "YES" ]]; then
  echo "ERROR: rollback is destructive. Set CONFIRM_ROLLBACK=YES after incident/change approval." >&2
  exit 2
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: tracked working-tree changes are not allowed during rollback." >&2
  exit 2
fi

MANIFEST="$ROOT/backups/$NAME/backup-manifest.json"
SUMS="$ROOT/backups/$NAME/SHA256SUMS"
if [[ ! -s "$MANIFEST" || ! -s "$SUMS" ]]; then
  echo "ERROR: backup manifest/checksums not found for: $NAME" >&2
  exit 3
fi

(
  cd "$ROOT/backups/$NAME"
  sha256sum -c SHA256SUMS
)

read_manifest() {
  python - "$MANIFEST" "$1" <<'PY'
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

SCHEMA="$(read_manifest schema)"
BACKUP_SOURCE_COMMIT="$(read_manifest source_commit)"
BACKUP_RELEASE_VERSION="$(read_manifest release_version)"
BACKUP_QUIESCED="$(read_manifest release_consistent_quiesce)"
ROLLBACK_FROM_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"

if [[ "$SCHEMA" != "grc-backup-manifest-v1" ]]; then
  echo "ERROR: unsupported backup manifest schema: $SCHEMA" >&2
  exit 3
fi
if [[ "$BACKUP_QUIESCED" != "true" ]]; then
  echo "ERROR: release rollback requires a quiesced pre-upgrade backup." >&2
  exit 3
fi
if [[ ! "$BACKUP_SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]] || \
   ! git cat-file -e "${BACKUP_SOURCE_COMMIT}^{commit}" 2>/dev/null; then
  echo "ERROR: backup source commit is invalid or unavailable locally." >&2
  exit 3
fi
if [[ -z "$BACKUP_RELEASE_VERSION" || "$BACKUP_RELEASE_VERSION" == "unknown" ]]; then
  echo "ERROR: release rollback requires a recorded source release version." >&2
  exit 3
fi
if [[ "$ROLLBACK_FROM_COMMIT" == "$BACKUP_SOURCE_COMMIT" ]]; then
  echo "Checkout is already at the backup source commit; proceeding with restore."
else
  echo "Switching checkout to exact rollback source commit: $BACKUP_SOURCE_COMMIT"
  git switch --detach "$BACKUP_SOURCE_COMMIT"
fi

# The currently running Bash process retains the validated rollback wrapper even
# after Git switches to the previous release. The restore script invoked below
# is therefore the restore implementation that belongs to that exact release.
# The backup directory and .env are ignored/untracked and remain available.
export CONFIRM_RESTORE=YES
export GRC_RELEASE_VERSION="$BACKUP_RELEASE_VERSION"
unset RESTORE_ALLOW_FORWARD_COMPATIBLE

if [[ ! -f scripts/pilot-restore.sh ]]; then
  echo "ERROR: rollback source release does not contain scripts/pilot-restore.sh." >&2
  exit 4
fi

echo "Restoring backup $NAME under source release $BACKUP_RELEASE_VERSION / $BACKUP_SOURCE_COMMIT (from $ROLLBACK_FROM_COMMIT)."
exec bash scripts/pilot-restore.sh "$NAME"

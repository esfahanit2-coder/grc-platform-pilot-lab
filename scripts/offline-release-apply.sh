#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
umask 077

MODE="${1:-}"
BUNDLE="${2:-}"
TRUSTED_PUBLIC_KEY="${3:-}"
INSTALL_ROOT="${4:-}"
EXTRA="${5:-}"
if [[ "$MODE" != "install" && "$MODE" != "update" ]]; then
  echo "Usage:" >&2
  echo "  $0 install <signed-bundle.tar.gz> <trusted-public-key.pem> <install-root> [production-env-file]" >&2
  echo "  $0 update  <signed-bundle.tar.gz> <trusted-public-key.pem> <install-root> [backup-name]" >&2
  exit 2
fi
if [[ -z "$BUNDLE" || -z "$TRUSTED_PUBLIC_KEY" || -z "$INSTALL_ROOT" ]]; then
  echo "ERROR: bundle, trusted public key and install root are required." >&2
  exit 2
fi
for command in docker git openssl python tar realpath; do
  command -v "$command" >/dev/null || { echo "ERROR: required offline prerequisite not found: $command" >&2; exit 2; }
done
BUNDLE="$(realpath "$BUNDLE")"
TRUSTED_PUBLIC_KEY="$(realpath "$TRUSTED_PUBLIC_KEY")"
INSTALL_ROOT="$(realpath -m "$INSTALL_ROOT")"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

python - "$BUNDLE" "$TMP" <<'PY'
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
    raise SystemExit("ERROR: bundle must contain exactly one top-level directory")
PY
STAGE="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d -print -quit)"
"$ROOT/scripts/offline-release-verify.sh" "$STAGE" "$TRUSTED_PUBLIC_KEY" >/dev/null

read_manifest() {
  python - "$STAGE/release-manifest.json" "$1" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
value = payload
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}
VERSION="$(read_manifest release_version)"
SOURCE_SHA="$(read_manifest source_commit)"

load_images() {
  while IFS=$'\t' read -r role reference archive expected_id; do
    [[ -n "$reference" ]] || continue
    echo "Loading $role image: $reference"
    docker load -i "$STAGE/$archive" >/dev/null
    actual_id="$(docker image inspect --format '{{.Id}}' "$reference" 2>/dev/null || true)"
    if [[ "$actual_id" != "$expected_id" ]]; then
      echo "ERROR: loaded image ID mismatch for $reference" >&2
      exit 4
    fi
  done < <(python - "$STAGE/metadata/images.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
for row in payload["images"]:
    print("\t".join([row["role"], row["reference"], row["archive"], row["image_id"]]))
PY
  )
}

REPOSITORY="$INSTALL_ROOT/repository"
RELEASE_DIR="$INSTALL_ROOT/release"

if [[ "$MODE" == "install" ]]; then
  if [[ -e "$INSTALL_ROOT" && -n "$(find "$INSTALL_ROOT" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "ERROR: install root must not already contain files: $INSTALL_ROOT" >&2
    exit 3
  fi
  mkdir -p "$INSTALL_ROOT" "$RELEASE_DIR"
  git init -q "$REPOSITORY"
  git -C "$REPOSITORY" fetch -q "$STAGE/source/grc-platform.bundle" \
    "refs/grc-release/$VERSION:refs/remotes/offline/$VERSION"
  git -C "$REPOSITORY" checkout -q --detach "$SOURCE_SHA"
  if [[ "$(git -C "$REPOSITORY" rev-parse HEAD)" != "$SOURCE_SHA" ]]; then
    echo "ERROR: source bundle checkout does not match signed source commit." >&2
    exit 4
  fi
  install -m 600 "$STAGE/release-manifest.json" "$RELEASE_DIR/release-manifest.json"
  install -m 600 "$STAGE/release-manifest.sig" "$RELEASE_DIR/release-manifest.sig"
  install -m 600 "$STAGE/metadata/images.json" "$RELEASE_DIR/images.json"
  install -m 600 "$TRUSTED_PUBLIC_KEY" "$RELEASE_DIR/trusted-release-public-key.pem"

  if [[ -n "$EXTRA" ]]; then
    ENV_FILE="$(realpath "$EXTRA")"
    python "$REPOSITORY/scripts/datacenter-env-validate.py" \
      --env "$ENV_FILE" \
      --release-version "$VERSION" >/dev/null
    install -m 600 "$ENV_FILE" "$REPOSITORY/.env"
  fi
  if [[ "${OFFLINE_INSTALL_START:-NO}" == "YES" && ! -s "$REPOSITORY/.env" ]]; then
    echo "ERROR: OFFLINE_INSTALL_START=YES requires a supplied production env file." >&2
    exit 4
  fi

  load_images
  echo "Offline release $VERSION installed and images preloaded at $INSTALL_ROOT."
  if [[ "${OFFLINE_INSTALL_START:-NO}" == "YES" ]]; then
    cd "$REPOSITORY"
    export DATACENTER_LOCAL_AI="${PILOT_LOCAL_AI:-NO}"
    CONFIRM_INSTALL=YES bash scripts/datacenterctl install
    echo "Offline release $VERSION started and verified without build or package/model download."
  else
    echo "No services were started. Review .env/TLS/model prerequisites, then follow docs/OFFLINE_RELEASE_AND_SUPPORT.md."
  fi
  exit 0
fi

if [[ ! -d "$REPOSITORY/.git" || ! -s "$RELEASE_DIR/release-manifest.json" || ! -s "$REPOSITORY/.env" ]]; then
  echo "ERROR: update requires an existing offline installation with repository, release manifest and .env." >&2
  exit 3
fi
if [[ ! -s "$RELEASE_DIR/release-manifest.sig" || ! -s "$RELEASE_DIR/trusted-release-public-key.pem" ]]; then
  echo "ERROR: current installed release signature metadata is incomplete." >&2
  exit 4
fi
if ! openssl dgst -sha256   -verify "$RELEASE_DIR/trusted-release-public-key.pem"   -signature "$RELEASE_DIR/release-manifest.sig"   "$RELEASE_DIR/release-manifest.json" >/dev/null 2>&1; then
  echo "ERROR: current installed release manifest signature is invalid." >&2
  exit 4
fi
OLD_VERSION="$(python - "$RELEASE_DIR/release-manifest.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["release_version"])
PY
)"
OLD_SHA="$(python - "$RELEASE_DIR/release-manifest.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["source_commit"])
PY
)"
if [[ "$(git -C "$REPOSITORY" rev-parse HEAD)" != "$OLD_SHA" ]]; then
  echo "ERROR: installed repository HEAD does not match the recorded current release." >&2
  exit 4
fi
if ! git -C "$REPOSITORY" diff --quiet || ! git -C "$REPOSITORY" diff --cached --quiet; then
  echo "ERROR: tracked local changes block an offline update." >&2
  exit 4
fi
git -C "$REPOSITORY" fetch -q "$STAGE/source/grc-platform.bundle" \
  "refs/grc-release/$VERSION:refs/remotes/offline/$VERSION"
if ! git -C "$REPOSITORY" cat-file -e "${SOURCE_SHA}^{commit}" 2>/dev/null; then
  echo "ERROR: signed target commit was not provided by the source bundle." >&2
  exit 4
fi
HISTORY_DIR="$RELEASE_DIR/history/$OLD_SHA"
mkdir -p "$HISTORY_DIR"
chmod 700 "$RELEASE_DIR/history" "$HISTORY_DIR" 2>/dev/null || true
for metadata_file in release-manifest.json release-manifest.sig trusted-release-public-key.pem images.json; do
  if [[ -s "$RELEASE_DIR/$metadata_file" ]]; then
    install -m 600 "$RELEASE_DIR/$metadata_file" "$HISTORY_DIR/$metadata_file"
  fi
done

TARGET_VALIDATOR="$TMP/datacenter-env-validate.py"
if ! git -C "$REPOSITORY" show "$SOURCE_SHA:scripts/datacenter-env-validate.py" > "$TARGET_VALIDATOR"; then
  echo "ERROR: signed target release does not contain the datacenter environment validator." >&2
  exit 4
fi
python "$TARGET_VALIDATOR" \
  --env "$REPOSITORY/.env" \
  --release-version "$OLD_VERSION" \
  --require-tls-files >/dev/null

load_images
git -C "$REPOSITORY" checkout -q --detach "$SOURCE_SHA"

BACKUP_NAME="${EXTRA:-pre-upgrade-${OLD_VERSION}-to-${VERSION}}"
cd "$REPOSITORY"
export GRC_RELEASE_VERSION="$VERSION"
export FROM_RELEASE_VERSION="$OLD_VERSION"
export PILOT_OFFLINE=YES
export PILOT_TLS=YES
export PILOT_LOCAL_AI="${PILOT_LOCAL_AI:-NO}"
export CONFIRM_UPGRADE=YES
if ! bash scripts/pilot-upgrade.sh "$OLD_SHA" "$BACKUP_NAME"; then
  echo "ERROR: offline update failed. Writers remain protected according to the upgrade phase." >&2
  echo "After approval, rollback with: CONFIRM_ROLLBACK=YES bash scripts/pilot-rollback.sh $BACKUP_NAME" >&2
  exit 5
fi
python - "$REPOSITORY/.env" "$VERSION" <<'PY'
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
seen = False
updated = []
for raw in lines:
    if raw.strip().startswith("GRC_RELEASE_VERSION="):
        updated.append(f"GRC_RELEASE_VERSION={version}")
        seen = True
    else:
        updated.append(raw)
if not seen:
    raise SystemExit("ERROR: GRC_RELEASE_VERSION is missing from the production environment file")
fd, tmp = tempfile.mkstemp(prefix=".env.release-", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(updated) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
PY
install -m 600 "$STAGE/release-manifest.json" "$RELEASE_DIR/release-manifest.json"
install -m 600 "$STAGE/release-manifest.sig" "$RELEASE_DIR/release-manifest.sig"
install -m 600 "$STAGE/metadata/images.json" "$RELEASE_DIR/images.json"
install -m 600 "$TRUSTED_PUBLIC_KEY" "$RELEASE_DIR/trusted-release-public-key.pem"
export DATACENTER_LOCAL_AI="${PILOT_LOCAL_AI:-NO}"
bash scripts/datacenterctl verify >/dev/null

echo "Offline update completed and verified: $OLD_VERSION -> $VERSION"
echo "Retain the previous signed bundle and backups until the release observation window is closed."

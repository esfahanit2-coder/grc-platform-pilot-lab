# Offline release, update and operator support handbook

This handbook is the implementation record for Issue #22 and the offline-release foundation reused by Issue #73. It defines the controlled path for preparing, signing, verifying, installing, updating and supporting GRC Platform in disconnected on-premise environments.

For the production datacenter operator contract, including configuration validation, first-tenant bootstrap, machine-readable verification, rollback decision rules, firewall expectations and sizing hooks, use [DATACENTER_OPERATIONS.md](DATACENTER_OPERATIONS.md).

The release bundle is designed so an approved target host does not need to download application packages, container images or AI models during installation/update. Host prerequisites such as Docker, Docker Compose, Git, Python, OpenSSL and standard archive/core utilities must be installed through the organization's normal operating-system provisioning process before the GRC release is transferred.

## 1. Trust and validation boundary

The repository provides:

- deterministic release manifest generation for identical staged payloads;
- SHA-256 coverage for every manifest-listed payload file;
- detached manifest signing with an organization-controlled private key;
- signature verification against a public key supplied separately from the bundle;
- fail-closed rejection of checksum, payload-set, manifest or signature mismatch;
- exact container image archives and recorded Docker image IDs;
- an exact Git source bundle for the release commit;
- CycloneDX SBOMs;
- references/digests for security reports without copying raw secret-scan results into distribution media;
- migration artifact inventory and configuration-template schema;
- install/update tooling that uses preloaded images and `--no-build` for the air-gapped path;
- secret-minimized support evidence collection.

The repository does **not** provide or claim:

- custody of the organization's production signing private key;
- an HSM/KMS/key ceremony;
- OS/Docker installation media;
- redistribution rights for third-party AI model weights;
- customer secrets, TLS private keys, production `.env`, database dumps or Evidence data inside a release bundle;
- real-site installation timing, HA failover or RPO/RTO evidence.

## 2. Required offline-host prerequisites

Provision these before isolating the target host:

- Linux supported by the organization's Docker policy;
- Docker Engine and Docker Compose 2.24.4 or later (required by the production TLS port replacement contract);
- Git;
- Python 3.12 or newer;
- OpenSSL;
- `tar`, `gzip`, `sha256sum`, `find` and normal GNU/core utilities;
- sufficient disk for all container images, PostgreSQL, object storage, backups and any separately approved local-AI models;
- approved TLS certificate/private key recovered through the organization's PKI process;
- approved production `.env` prepared separately from the release bundle;
- encrypted backup media outside the application data volumes.

No release script installs these prerequisites from the internet.

## 3. Bundle contents and manifest contract

`scripts/offline-release-build.sh` creates a staged candidate under `artifacts/offline-release/<version>/`.

The candidate includes:

- `release-manifest.json` using schema `grc-offline-release-manifest-v1`;
- exact image archives for backend, frontend, PostgreSQL/pgvector, Redis, object storage, optional Ollama runtime and Nginx gateway;
- `metadata/images.json` with image reference, archive and exact image ID;
- `source/grc-platform.bundle` containing the release commit and reachable history;
- backend/frontend CycloneDX SBOMs;
- `metadata/security-evidence.json` containing SHA-256 references to the generated security reports while intentionally excluding the raw reports themselves;
- `metadata/migrations.json` containing the migration-file inventory and combined tree digest;
- `metadata/config-schema.json` describing the public pilot config template and which variables are required/sensitive;
- `metadata/local-ai-models.json` with `distribution_mode=reference-only`;
- public runtime configuration templates and this handbook.

The manifest contains no timestamp, so its bytes are stable for the same version/source/payload metadata. Every payload file is listed by path, byte size and SHA-256. Extra/missing files, symlinks and checksum changes are rejected.

### Security-report boundary

The release gate produces Bandit, repository secret-scan and container scan reports. Those raw files stay in the approved CI/security evidence store because a secret-scanner finding may itself contain sensitive material. The offline bundle records their names and SHA-256 digests so the release can be correlated to retained security evidence without redistributing potentially sensitive scan output.

## 4. Build a release candidate

Run on the controlled online/release-build workstation after the matching Release Gate has passed and its SBOM/security files are available locally:

```bash
export OFFLINE_RELEASE_SBOM_DIR=/approved/release-evidence/sbom
export OFFLINE_RELEASE_SECURITY_DIR=/approved/release-evidence/security
bash scripts/offline-release-build.sh v1.0.0-rc1 <exact-release-commit>
```

The builder:

1. requires a clean tracked worktree and exact source commit;
2. builds version-tagged backend/frontend images;
3. pulls only the explicitly pinned infrastructure images from `docker-compose.pilot.yml`;
4. exports each exact image to an archive;
5. records the Docker image IDs/digests;
6. creates an exact Git source bundle;
7. copies SBOMs and public runtime templates;
8. hashes but does not embed raw security scan reports;
9. generates migration/config/model-reference metadata;
10. generates and immediately verifies the deterministic release manifest.

The output at this point is an **unsigned candidate** and is not approved distribution media.

## 5. Signing and key-management boundary

The production signing private key must be created, stored, backed up, rotated and revoked under the organization's release-signing policy. Prefer an offline signing workstation/HSM-backed process where available. The private key must never be committed to this repository, stored in the release stage, embedded in CI configuration or transferred to the target application host.

The repository signing helper deliberately refuses a private key path inside the repository.

Sign a prepared candidate:

```bash
bash scripts/offline-release-sign.sh \
  artifacts/offline-release/v1.0.0-rc1 \
  /secure/offline-signing/release-private-key.pem
```

This creates `release-manifest.sig` and a normalized `v1.0.0-rc1-offline-signed.tar.gz` plus an outer SHA-256 file.

The operator's trusted public key/fingerprint must arrive by an independent trusted channel. A public key copied from the same untrusted release media is **not** by itself a trust anchor.

## 6. Verify before installation

Verification is mandatory before loading any container image:

```bash
bash scripts/offline-release-verify.sh \
  v1.0.0-rc1-offline-signed.tar.gz \
  /etc/grc/trust/release-public-key.pem
```

Verification fails closed when:

- the detached signature does not validate;
- the manifest schema/source commit is invalid;
- required metadata is missing or differs from the signed manifest;
- any payload checksum/size differs;
- an expected payload file is missing;
- an unlisted payload file or symlink appears;
- local-AI metadata attempts to embed model bytes.

Do not use an override to bypass a failed verification. Re-acquire the release from the approved source and investigate the discrepancy.

## 7. Fresh air-gapped installation

Prepare production secrets outside the bundle:

```bash
cp .env.pilot.example /secure/staging/grc-production.env
chmod 600 /secure/staging/grc-production.env
```

Set all real values, including `GRC_RELEASE_VERSION` to the exact approved version, and remove every `replace-with-...` placeholder.

Install and preload without starting services:

```bash
bash scripts/offline-release-apply.sh install \
  v1.0.0-rc1-offline-signed.tar.gz \
  /etc/grc/trust/release-public-key.pem \
  /opt/grc \
  /secure/staging/grc-production.env
```

The helper verifies the signed bundle first, loads image archives, verifies every loaded image ID, initializes the Git repository from the bundled source, checks out the signed source commit and installs the supplied `.env` with restrictive permissions.

After TLS paths and any local model prerequisites are ready, start through the production operator entrypoint:

```bash
cd /opt/grc/repository
CONFIRM_INSTALL=YES bash scripts/datacenterctl install
```

This path validates the environment/TLS files, requires exact preloaded image references, starts with no build or pull, and runs machine-readable datacenter verification.

Alternatively set `OFFLINE_INSTALL_START=YES` with the apply helper after all host prerequisites are ready.

## 8. Offline update

Keep the previous signed release bundle until the new release observation window closes.

Run the update from the new signed bundle:

```bash
bash /opt/grc/repository/scripts/offline-release-apply.sh update \
  v1.0.0-offline-signed.tar.gz \
  /etc/grc/trust/release-public-key.pem \
  /opt/grc \
  pre-upgrade-v1.0.0
```

The update helper:

1. verifies the new bundle/signature;
2. loads every new image and verifies image IDs;
3. verifies the installed Git HEAD matches the recorded current release;
4. fetches the new source commit only from the signed Git bundle;
5. switches to the signed target commit;
6. invokes `pilot-upgrade.sh` with `PILOT_OFFLINE=YES`;
7. requires all target images to already exist locally;
8. audits migrations against the live schema;
9. creates a quiesced rollback backup with the old release version/commit;
10. applies audited migrations;
11. starts the target with `--no-build` and waits for readiness;
12. updates installed release metadata only after success.

The offline path never runs `docker build`, `docker pull`, `pip`, `npm` or model download commands on the target host.

## 9. Rollback

Rollback remains backup-based. Do not treat Django reverse migrations as the normal release rollback path.

If an update fails after migration begins, `pilot-upgrade.sh` leaves writers protected and reports the approved command:

```bash
CONFIRM_ROLLBACK=YES bash scripts/pilot-rollback.sh <pre-upgrade-backup-name>
```

The rollback helper verifies backup checksums/manifest, reads the recorded source commit **and release image version**, switches to that exact source commit and invokes that release's restore implementation. Preserve/reload the previous signed bundle if the previous release images are no longer present locally.

For the first transition from a legacy release that predates this offline-bundle contract, rehearse the legacy rollback separately and retain all legacy source/image prerequisites; no claim is made that an old release can retroactively gain the new no-download rollback behavior.

## 10. Local AI in disconnected environments

The GRC release bundle includes the pinned Ollama **runtime image** when local AI is in scope, but it does not include third-party model weights.

`metadata/local-ai-models.json` is reference-only. For each approved model, the operator should retain separate controlled-media metadata such as:

- provider/runtime (`ollama`, private vLLM, etc.);
- exact model name/version;
- file/blob SHA-256 or approved content digest;
- original source/provenance;
- license/terms reference;
- internal approval/evidence that local possession/use is allowed;
- classification boundary and allowed data classes.

Model bytes are transferred under their own approved licensing/procurement process and preloaded before isolation. The application stack does not download models at startup.

## 11. Operator troubleshooting

Use the least sensitive evidence first.

### Startup / Compose

- verify release signature and manifest again;
- confirm `GRC_RELEASE_VERSION` matches the installed manifest;
- run `docker compose ... config`;
- confirm every expected image exists with `docker image inspect`;
- inspect `docker compose ... ps` and health state.

### PostgreSQL / migrations

- run `pilot_readiness`;
- run `python manage.py release_migration_plan --require-reversible` from the exact release backend/ops image before a controlled migration;
- never edit migration history directly to make an update pass;
- for major PostgreSQL version changes use a separately approved PostgreSQL upgrade procedure.

### Object storage

- verify the S3 endpoint/bucket is reachable from the backend network;
- do not send object contents to support by default;
- use existing backup/archive checksums to distinguish metadata vs object-byte problems.

### Redis / workers

- check Redis service health before workers;
- inspect worker/beat service state;
- do not assume Redis is authoritative GRC data, but queued work and throttle state can be affected by Redis loss/failover.

### TLS / browser auth

- verify certificate/key paths exist with appropriate permissions;
- confirm the hostname matches `DJANGO_ALLOWED_HOSTS`, CORS and CSRF trusted origins;
- confirm the browser sees the approved certificate and HTTPS forwarded scheme.

### Local AI

- confirm the runtime image exists locally;
- confirm the approved model was preloaded separately;
- confirm tenant provider model names match those preloaded artifacts;
- run `pilot_readiness --ai-provider-id <uuid>` with internet egress disabled for the final acceptance proof.

### Connectors

- use Connector Operations health/sync history first;
- verify target DNS/network reachability and secret-reference names;
- never paste API tokens, passwords or full Evidence payloads into a support ticket.

## 12. Support evidence without secrets/customer data

For the production datacenter support package run:

```bash
bash scripts/datacenterctl support
```

The datacenter collector includes secret-safe verification, service/dependency state, migration status, operational status and a bounded allowlist of structured error metadata. It never persists raw logs. The older scripts/support-evidence.sh remains a lower-level pilot evidence helper.

It intentionally excludes:

- `.env` contents and environment-variable values;
- TLS private keys/certificates;
- database dumps;
- object-store/Evidence contents;
- connector credentials/tokens;
- application/service logs;
- customer records;
- AI prompts/responses.

If logs are required for escalation, collect only the minimum affected service/time window, review/redact them locally, and transfer them through the organization's approved support-data channel. Do not automate uploading logs or customer data from the GRC host.

## 13. Release evidence to retain

For each approved offline release retain outside the application host as appropriate:

- exact release version and source SHA;
- successful CI + Release Gate evidence for that SHA/tag;
- signed bundle and outer SHA-256;
- trusted signing public-key fingerprint/key version;
- `release-manifest.json` + detached signature;
- SBOMs;
- retained security reports matching the manifest-recorded SHA-256 values;
- change/approval record;
- install/update/rollback observations;
- pre-upgrade backup manifest/checksums when an update occurs.

Do not delete the previous approved signed bundle or rollback backup until the new release observation window is formally closed.

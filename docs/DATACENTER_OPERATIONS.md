# Datacenter installation, upgrade and recovery runbook

This runbook is the repository-side implementation record for Issue #73 under the Datacenter-ready v1 program (#68).

It defines the supported operator path for installing and operating GRC Platform in a customer datacenter without developer-only shortcuts. The clean-host execution, destructive restore drill and measured RPO/RTO remain external proof gates under Issue #7; repository CI must not be used as a substitute for those measurements.

## 1. Supported deployment contract

The production datacenter path is based on:

- an exact release source commit;
- version-tagged application images and pinned infrastructure images;
- a signed offline release manifest and separately trusted public key;
- a production environment file that passes scripts/datacenter-env-validate.py;
- the TLS Compose override;
- scripts/datacenterctl as the normal operator entrypoint;
- release-consistent PostgreSQL + object-storage backup before upgrade;
- machine-readable post-install/post-upgrade verification;
- secret-safe support bundles.

The same signed package may be used on a connected host. Internet access is never required by the application install/update path once the signed bundle, approved prerequisites, certificates, secrets and any separately licensed local-AI model artifacts are present.

## 2. Host prerequisites

Provision these through the customer's normal server/OS process before the GRC package is applied:

- supported Linux host under the customer's hardening policy;
- Docker Engine with a reachable daemon;
- Docker Compose **2.24.4 or later**;
- Git;
- Python 3.12 or later;
- OpenSSL;
- tar, gzip, sha256sum, find, realpath and standard GNU/core utilities;
- approved DNS/NTP/PKI services as required by the customer environment;
- encrypted backup storage separated from the application data volumes;
- sufficient storage and memory for the measured workload profile.

Compose 2.24.4 is the minimum because the TLS override uses !override to replace the non-TLS development/pilot port list instead of accidentally merging it.

No project script installs OS packages or Docker from the internet.

## 3. Network and firewall expectations

### Inbound to the host

In the production TLS composition:

- TCP/443: required application/API access;
- TCP/80: optional HTTP-to-HTTPS redirect path; it may be blocked if the customer requires HTTPS-only access and does not need redirect behavior.

The TLS override replaces the base pilot 8080 mapping. Port 8080 must not be exposed in the rendered production/TLS Compose model.

### Internal Compose network only

These are not published to the host by the production composition:

- PostgreSQL: 5432;
- Redis: 6379;
- S3-compatible object store: 8333;
- Django backend: 8000;
- Next.js frontend: 3000;
- optional Ollama: 11434.

Do not add host mappings for these services as a troubleshooting shortcut.

### Outbound

A fully air-gapped deployment requires no Internet egress for install/start/update. Customer-specific outbound flows may still be needed for explicitly enabled features such as SMTP, AD/LDAP, FortiGate, Veeam, Tenable/Nessus, external S3-compatible storage, SIEM, NTP/DNS or a private AI endpoint. Permit only the approved destination/port pairs for the features actually enabled.

## 4. Production configuration

Start from .env.pilot.example, but treat it only as a schema/template.

Set at minimum:

- exact GRC_RELEASE_VERSION;
- Django secret and audit-integrity key;
- real hostname, CORS and CSRF origins;
- PostgreSQL password;
- Redis/Celery endpoints;
- operational metrics bearer token;
- S3 endpoint/bucket/access credentials;
- dedicated MFA Fernet key;
- production TLS certificate/key paths;
- optional SMTP and connector secret references.

The production file must not contain template placeholders and must not grant group/other filesystem access (use mode 0600 or stricter).

Validate without exposing secret values:

~~~bash
python scripts/datacenter-env-validate.py \
  --env .env \
  --release-version <approved-version> \
  --require-tls-files
~~~

The validator checks production mode, secure cookie/redirect controls, required secret presence/shape, explicit hosts/origins, Evidence download fail-closed posture, S3 consistency, SMTP constraints when enabled, exact release version, TLS file/private-key permissions, certificate parse/expiry, private-key parse, and certificate/private-key public-key matching. It emits grc-datacenter-config-validation-v1 JSON and never emits secret values.

## 5. TLS and PKI

Production datacenter startup always uses docker-compose.pilot.tls.yml.

Provide TLS_CERT_PATH and TLS_KEY_PATH. The private key must not grant group/other access. Certificate and key material are not included in release bundles, backups or support bundles; recovery is through the customer's PKI/key-recovery process.

Before exposing the service, validate certificate chain, hostname/SAN, renewal procedure and reverse-proxy behavior under the real customer trust store. Full `datacenterctl verify` performs an external HTTPS probe from the host to `/api/v1/health/live` and `/api/v1/health/ready`, so the configured hostname must resolve correctly and the issuing CA must be trusted by the host. For a controlled Pilot with a private CA that is not installed system-wide, export `GRC_VERIFY_CA_CERT=/path/to/approved-ca.pem` or pass `--ca-cert` to `datacenterctl verify`; production rollout should use the organization's approved trust-store procedure.

## 6. Signed air-gapped package

The canonical disconnected release process remains:

1. build the candidate with scripts/offline-release-build.sh;
2. retain matching CI security evidence and SBOMs;
3. sign with scripts/offline-release-sign.sh using the controlled signing key;
4. transfer the signed archive and trusted public key through approved media/channels;
5. verify with scripts/offline-release-verify.sh before any image is loaded;
6. apply with scripts/offline-release-apply.sh.

The package contains exact image archives, source Git bundle, manifest metadata and public templates. It does not contain customer secrets, TLS private keys, database backups, Evidence/customer documents or third-party AI model weights.

## 7. Fresh installation

Prepare a production environment file whose GRC_RELEASE_VERSION exactly matches the signed bundle.

Install and preload:

~~~bash
bash scripts/offline-release-apply.sh install \
  <signed-bundle.tar.gz> \
  <trusted-release-public-key.pem> \
  /opt/grc \
  <production-env-file>
~~~

This validates the environment against the signed release before copying it into the installation.

After the TLS files and any separately approved local-AI models are present:

~~~bash
cd /opt/grc/repository
CONFIRM_INSTALL=YES bash scripts/datacenterctl install
~~~

The install command:

1. requires explicit confirmation;
2. validates the production environment and TLS files;
3. checks Docker, Git, OpenSSL and Compose prerequisites;
4. validates the installed signed manifest, source commit and signed Docker image identities before startup;
5. validates the merged Compose model;
6. rejects mutable/unversioned image references and requires every resolved image to be preloaded;
7. starts with --no-build --pull never --wait;
8. validates the live 80/443 gateway mapping and runs the full machine-readable datacenter verification.

For a one-step prepared-host install, OFFLINE_INSTALL_START=YES on offline-release-apply.sh install invokes the same datacenterctl install path.

## 8. First tenant and administrator bootstrap

Do not create the first tenant or administrator through ad-hoc Django shell commands.

Run:

~~~bash
bash scripts/datacenterctl bootstrap \
  --tenant-code <customer-code> \
  --tenant-name "<customer-name>" \
  --admin-username <admin-login> \
  --admin-email <admin-email>
~~~

The password is prompted twice without terminal echo and is piped to the backend process; it is not placed in command-line arguments, shell history, Git or the command output.

bootstrap_datacenter creates or safely reconciles:

- the Tenant;
- active TenantMembership;
- system RBAC catalog/roles;
- whole-tenant tenant_admin scope;
- root Company organization unit.

By default it refuses a first-install bootstrap if an unrelated tenant already exists.

After bootstrap, enroll MFA and apply the customer's security policy before operational use.

## 9. Installation verification

Run:

~~~bash
bash scripts/datacenterctl verify \
  --json-out artifacts/datacenter-verification.json
~~~

The report schema is grc-datacenter-verification-v1.

It checks and reports:

- production configuration contract;
- Docker Engine availability/version;
- Docker Compose minimum/capabilities;
- detached release-manifest signature against the separately trusted installed public key;
- exact signed source commit plus a clean tracked worktree/index;
- signed image-metadata hash/size and Docker image IDs;
- merged Compose validity;
- immutable/preloaded image references;
- PostgreSQL, Redis, object store, backend, worker, beat, frontend and gateway service state;
- pending migration state;
- Django `check --deploy` against the actual runtime settings, with any deployment warnings retained as a review count while hard errors fail verification;
- application readiness including DB/pgvector, Redis and S3;
- external HTTPS live/ready probes with hostname and CA validation;
- operational health JSON.

No secret values or customer Evidence payloads are included.

A repository/CI self-test proves the verifier's parsing/aggregation logic; only the real target host can prove actual network, certificate, storage and service behavior.

## 10. Backup

For an operational backup:

~~~bash
bash scripts/datacenterctl backup <backup-name>
~~~

The datacenter wrapper defaults to a quiesced, release-consistent backup.

The existing backup primitive captures:

- PostgreSQL custom-format dump;
- S3-level object-store archive/checksums;
- source commit/release metadata;
- image list;
- backup manifest/checksums;
- protected configuration copy required for recovery.

The backup directory contains secrets and customer data. Store it only on approved encrypted recovery media and keep it out of Git/support tickets.

## 11. Upgrade

The signed offline update path is the preferred production path:

~~~bash
bash scripts/offline-release-apply.sh update \
  <new-signed-bundle.tar.gz> \
  <trusted-release-public-key.pem> \
  /opt/grc \
  <pre-upgrade-backup-name>
~~~

Before any migration it verifies the currently installed signed release/source/image state, verifies the target bundle with the operator-supplied trusted key, validates the existing production configuration against the target release schema, snapshots the current signed release metadata, loads/verifies target images and creates a quiesced rollback backup.

The upgrade primitive then:

1. checks current readiness;
2. audits target migrations against the live schema;
3. blocks unsafe migration plans from the normal reversible path;
4. applies the target images/migrations;
5. starts the exact target release without download in offline mode;
6. waits for readiness;
7. records the upgrade observation.

After successful upgrade the apply helper atomically changes only GRC_RELEASE_VERSION in .env, replaces installed signed-release metadata and reruns datacenter verification.

Do not delete the previous signed bundle or rollback backup until the observation window is formally closed.

## 12. Rollback decision rules

Rollback is explicit; "run the old image" is not a sufficient recovery plan.

### Application-only return is allowed only when

- failure occurs before target schema migration begins;
- the target release has not written incompatible application/database state;
- no object-storage mutation requiring coordinated recovery has occurred;
- the currently installed schema remains compatible with the previous application release.

The upgrade script already attempts to restart the existing release for safe failures before migration.

### Backup-based rollback is required when

- target migration began;
- schema compatibility cannot be proven;
- the target may have written state under the new schema;
- database and Evidence/object state must be returned to the same recovery point;
- the upgrade tool explicitly reports the backup rollback path.

Use:

~~~bash
CONFIRM_ROLLBACK=YES bash scripts/datacenterctl rollback <pre-upgrade-backup-name>
~~~

The underlying rollback verifies the backup manifest/checksums, switches to the exact recorded source commit and invokes that release's restore implementation. Before each signed update the operator package also snapshots the active signed release metadata under the previous source SHA; after rollback it restores that manifest/signature/trusted key (and signed image metadata when available) as the active release record.

### Object-storage consistency

The PostgreSQL dump and object-store archive from the quiesced backup form one recovery point. Do not restore one while keeping post-backup state from the other unless an independently reviewed application-consistency procedure explicitly proves that combination safe.

### PostgreSQL major versions

A backup cannot be restored through this helper across a PostgreSQL major-version mismatch. Such a change requires a separately approved PostgreSQL upgrade/recovery procedure.

## 13. Destructive restore

A restore requires explicit approval:

~~~bash
CONFIRM_RESTORE=YES bash scripts/datacenterctl restore <backup-name>
~~~

The restore path validates checksums/manifest/source compatibility and PostgreSQL major version, stops writers, restores PostgreSQL and object storage, applies the approved migration path, restarts the application and runs readiness.

Issue #7 must execute this on a clean/replacement real host and measure the organization's actual RPO/RTO using controlled application markers. Do not derive an RPO/RTO promise from script duration or CI.

## 14. Secret-safe support bundle

Run:

~~~bash
bash scripts/datacenterctl support
~~~

The generated grc-datacenter-support-bundle-v1 includes:

- installation/config schema verification status;
- release/source version identifiers;
- service and dependency status;
- migration status;
- operational status;
- at most 100 recent structured error metadata entries from a bounded time window.

The collector never persists raw logs. It allowlists only low-risk fields such as timestamp, level, request ID, method, path, status, duration and error type.

Excluded by design:

- .env and environment values;
- TLS certificates/private keys;
- database dumps;
- object-store/Evidence contents;
- connector/SMTP credentials;
- raw service logs;
- customer records;
- AI prompts/responses/knowledge payloads.

Review the resulting archive under the customer's support-data policy before transfer.

## 15. Provisional sizing guidance

No vCPU, RAM, IOPS, user-count or throughput guarantee is asserted until representative benchmarks and the real clean-host validation are available.

Use these workload classes only to select the measurement plan:

| Profile | Intended shape | What must be measured before production sizing |
| --- | --- | --- |
| Small | Single organization, modest user concurrency, limited Evidence volume, no or light local AI | PostgreSQL working set/latency, backup window, S3 growth/throughput, Redis/Celery queue age, backend response latency |
| Medium | Multiple teams/sites, regular assessments/audits, recurring connectors and reports | All Small metrics plus worker concurrency, connector burst behavior, report-generation load, restore duration |
| Large / Enterprise | Multiple business units/sites, high Evidence volume, frequent integrations, SIEM/metrics consumers, optional local AI | Dedicated DB/storage performance, horizontal worker/backend needs, failure-domain design, backup/restore throughput, retention growth, AI isolation/capacity |

Component-specific hooks:

- PostgreSQL/pgvector: active dataset, index growth, query latency, IOPS and backup/restore rate;
- Redis: memory, queue depth/age, throttle/cache requirements;
- Celery: task duration, concurrency and backlog during connector/report bursts;
- backend: request concurrency and p95/p99 latency under representative workflows;
- frontend/gateway: concurrent sessions and TLS termination overhead;
- S3-compatible storage: Evidence growth, object count, upload/download throughput and recovery rate;
- local AI: model-specific RAM/VRAM, context size, concurrency and latency measured separately from core GRC.

Production capacity must be signed off from measured customer workload plus growth/retention assumptions, not from placeholder numbers.

## 16. Acceptance boundary

Repository CI can prove syntax, static contracts, tests, release-manifest tamper resistance and the non-secret self-tests of the datacenter tooling.

Before #73/#74 can be treated as customer-ready evidence, the relevant exact-head CI and Release Gate must be green.

Before production rollout, the external gates still require:

- clean-host install on target infrastructure;
- real certificate/browser verification;
- destructive restore with measured RPO/RTO (#7);
- authorized live connector validation (#6);
- independent security validation/pentest (#8);
- authorized standards/content (#5);
- organization-approved image/digest and repository governance controls.

A green repository is necessary but not sufficient evidence of those real-world outcomes.

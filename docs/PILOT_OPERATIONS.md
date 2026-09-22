# Clean-host pilot operations runbook

This runbook is the execution record for Issue #7. It distinguishes repository/CI readiness from observations that must be measured on an actual pilot host.

## Current validation boundary

The repository can prove configuration syntax, application tests, object-archive round trips, AI provider switching/disable behavior and security gates in CI. It cannot prove clean-host timing, host networking, real certificates, real backup media throughput or a local model until those are exercised on the target environment.

Do not close Issue #7 until the **Measured pilot observations** section is populated from a real drill.

## Runtime composition

`docker-compose.pilot.yml` provides:

- PostgreSQL 18 + pgvector;
- Redis with append-only persistence;
- bundled S3-compatible object storage using pinned SeaweedFS 4.47;
- Django backend;
- Celery worker and beat;
- Next.js frontend;
- Nginx gateway;
- optional pinned Ollama 0.34.1 under the `local-ai` profile;
- an `ops` profile used only for backup/restore commands.

The Django application still talks only to the S3 abstraction. An approved external S3-compatible service can replace the bundled object store through `.env` without changing domain code.

## 1. Clean-host prerequisites

Prepare a Linux host with:

- Docker Engine and Docker Compose v2;
- enough disk for PostgreSQL, evidence objects, container images, backups and optional local models;
- DNS/name resolution for the chosen GRC hostname;
- an approved TLS certificate and private key;
- encrypted backup storage separate from the application data volumes;
- no inbound exposure of PostgreSQL, Redis, object storage or Ollama ports.

Copy the repository at the release commit to the host. Do not copy a developer `.env`.

## 2. Production environment file

```bash
cp .env.pilot.example .env
chmod 600 .env
```

Replace every placeholder secret and set the real hostname/origin values. In particular verify:

- `DJANGO_SECRET_KEY`;
- `POSTGRES_PASSWORD`;
- `S3_ACCESS_KEY` / `S3_SECRET_KEY`;
- `MFA_ENCRYPTION_KEY`;
- `DJANGO_ALLOWED_HOSTS`;
- `CORS_ALLOWED_ORIGINS`;
- `CSRF_TRUSTED_ORIGINS`.

For the bundled object store keep:

- `S3_ENDPOINT_URL=http://objectstore:8333`;
- `S3_USE_SSL=0`.

This HTTP hop stays on the private Compose network. User/browser traffic must use the TLS gateway.

## 3. TLS gateway

Keep certificate material outside Git, for example:

```text
runtime/tls/server.crt
runtime/tls/server.key
```

Set permissions according to the host security policy and set `TLS_CERT_PATH` / `TLS_KEY_PATH` in `.env` if different.

Validate the merged Compose configuration before startup:

```bash
docker compose --env-file .env \
  -f docker-compose.pilot.yml \
  -f docker-compose.pilot.tls.yml \
  config >/dev/null
```

Start the core stack:

```bash
docker compose --env-file .env \
  -f docker-compose.pilot.yml \
  -f docker-compose.pilot.tls.yml \
  up -d --build --wait
```

Verify that HTTP redirects to HTTPS and that browser/API traffic presents the approved certificate. Confirm authentication cookies are `Secure`, CSRF requests succeed only for the configured trusted origin, and the backend sees `X-Forwarded-Proto: https`.

## 4. Dependency readiness

Run the non-destructive probe from the backend container:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml \
  exec -T backend python manage.py pilot_readiness
```

A final pilot acceptance run must show:

- PostgreSQL reachable;
- pgvector enabled;
- Redis reachable;
- configured S3 bucket reachable;
- production secure-cookie checks passing.

The authenticated product UI exposes the same operational baseline at
`/admin/operations` for users with whole-tenant `security.view`. The endpoint
`/api/v1/operations/status/` is intentionally not public and does not return
credentials, raw dependency URLs or exception messages.

For shell/support workflows, collect the same secret-safe JSON without a user
session:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml \
  exec -T backend python manage.py operational_status --json
```

The async heartbeat is dispatched by Celery beat every minute and must be
executed by a worker, so staleness detects a break in the beat → broker → worker
round trip. Configure thresholds in `.env` with
`OPS_ASYNC_HEARTBEAT_MAX_AGE_SECONDS`, `OPS_BACKUP_MAX_AGE_HOURS` and
`OPS_CELERY_QUEUE_WARN_DEPTH`.

Review service state and recent logs:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml ps
docker compose --env-file .env -f docker-compose.pilot.yml logs --tail=200 backend worker beat frontend gateway objectstore
```

## 4A. Evidence malware scanner boundary

Production Evidence downloads are fail-closed when `EVIDENCE_REQUIRE_CLEAN_DOWNLOAD=1`. File uploads enter a server-owned `pending` quarantine state; API clients cannot set or erase malware scan state. The built-in integration can stream the exact S3 object to an approved `clamd` endpoint using ClamAV's `INSTREAM` protocol without writing the Evidence payload to application-host disk.

The GRC application intentionally does **not** deploy or update antivirus signatures. Scanner infrastructure, signature/database updates, licensing, network placement and offline update media remain an operational/security responsibility. ClamAV documents that its TCP `clamd` socket is not authenticated or encrypted, so do not expose it to an untrusted network. Use an approved private/protected path.

Keep the scanner disabled until that path exists:

```dotenv
EVIDENCE_MALWARE_SCANNER=disabled
EVIDENCE_REQUIRE_CLEAN_DOWNLOAD=1
```

When an authorized internal `clamd` service is available, configure:

```dotenv
EVIDENCE_MALWARE_SCANNER=clamd
EVIDENCE_MALWARE_SCAN_AUTOSUBMIT=1
CLAMD_HOST=<approved-private-clamd-host>
CLAMD_PORT=3310
CLAMD_TIMEOUT_SECONDS=15
CLAMD_CHUNK_SIZE=1048576
```

The Celery worker automatically submits new uploaded Evidence files. Scanner timeout/unavailability/object-read failures are retried within the configured bound; exhausted retries, malformed scanner replies, integrity mismatch, scanner-reported errors and infected results remain non-downloadable. A `clean` result is accepted only when the bytes scanned by the application match the Evidence record's stored size and SHA-256.

For a controlled manual retry after restoring the scanner path:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml \
  exec -T backend python manage.py scan_evidence_malware <EVIDENCE_UUID>
```

Validate the real environment before security sign-off:

- upload a harmless approved test file and verify `pending/scanning -> clean`;
- confirm the exact Evidence SHA-256 remains unchanged and the download becomes available only after `clean`;
- use the organization's approved malware-test procedure to prove an infected result remains quarantined; do not use uncontrolled malicious samples;
- disconnect or stop the scanner and verify uploaded files remain non-downloadable through retry exhaustion;
- review `evidence.malware_scan` audit events for clean/infected/error outcomes;
- verify the scanner/signature update process works under the target network and offline-update policy.

These repository controls improve the software boundary but do not complete Issue #8 by themselves. Real scanner deployment/validation, audit-storage integrity validation, independent penetration testing and final security sign-off remain external acceptance evidence.


## Datacenter observability

The deployment exposes two different operational surfaces:

1. `/api/v1/operations/status/` — authenticated human/operator JSON status, requiring whole-tenant `security.view`.
2. `/api/v1/operations/metrics/` — Prometheus-compatible deployment metrics. It contains **no tenant, user, object, framework, evidence or customer-content labels**.

In production, metrics fail closed unless `OPS_METRICS_TOKEN` is configured. Configure the scraper with:

```text
Authorization: Bearer <OPS_METRICS_TOKEN>
```

Do not publish the metrics route directly to an untrusted network. Prefer the monitoring VLAN or reverse-proxy allowlist used by the customer's observability platform.

The metrics surface is intentionally bounded to deployment health, fixed component names, queue depth and operational-signal age. Do not add tenant, user or object identifiers as Prometheus labels.

Application request logs are emitted as one-line JSON. They include request id, method, path, status and duration. Request bodies, query strings, tenant/customer payloads and authentication headers are not logged by the request middleware. The formatter also redacts common credential patterns and strips URL userinfo.

### SIEM audit export

Users or integrations with whole-tenant `audit.view` can pull a bounded audit envelope from:

```text
GET /api/v1/audit-events/export/?after_sequence=0&limit=500
```

For line-oriented ingestion:

```text
GET /api/v1/audit-events/export/?after_sequence=0&limit=500&format=jsonl
```

The JSONL response returns cursor headers:

- `X-GRC-Next-After-Sequence`
- `X-GRC-Has-More`

The SIEM export deliberately omits `old_data`, `new_data`, free-form metadata and customer payload content. It includes the append-only integrity chain fields so the receiver can retain sequence/hash evidence.

A SIEM collector should persist the last accepted `chain_sequence` and request only later events. Keep authentication at the application/API boundary and additionally restrict network access according to the customer's monitoring/SIEM zone policy.
\n\n
## SMTP notification delivery

Email is a **delivery channel over the authoritative in-app Notification record**. Email success or failure never changes the underlying Action, Document approval, Workflow or operational state.

Enable SMTP only after the customer's relay is available:

```text
NOTIFICATION_EMAIL_ENABLED=1
EMAIL_HOST=smtp.example.internal
EMAIL_PORT=587
EMAIL_HOST_USER=<secret-backed username>
EMAIL_HOST_PASSWORD=<secret-backed password>
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=grc@example.internal
APP_BASE_URL=https://grc.example.internal
```

Keep `EMAIL_HOST_PASSWORD` only in the deployment secret store or protected environment file. It is not stored in the database.

The product currently produces email-capable notifications for:

- Action assignment/reassignment;
- Actions due soon;
- Overdue Actions;
- Document approval stages;
- Deployment operational alerts for users with whole-tenant `security.view`.

Before sending, the worker re-checks that the target user is active, still has an active membership in the Notification tenant and still has a current email address. Invalid recipients are marked `skipped` rather than sent.

Delivery state is separate from Notification business state. Authorized operators with whole-tenant `security.view` can inspect:

```text
GET /api/v1/notification-deliveries/
GET /api/v1/notification-deliveries/?status=failed
```

A failed delivery can be retried with:

```text
POST /api/v1/notification-deliveries/<delivery-id>/retry/
```

Retries are also scheduled automatically. Only the exception **type** is persisted; raw SMTP exceptions, relay URLs and credentials are not stored in delivery diagnostics.

SMTP is an at-least-once transport. Each delivery uses a stable Message-ID derived from its delivery UUID, but the remote relay remains responsible for its own duplicate handling if a process fails after SMTP acceptance and before local acknowledgement.

For customer acceptance, verify at least one successful Assignment email, one Approval email, one failed-relay retry and one revoked-membership skip without exposing real credentials in GitHub evidence.


## 5. Local AI / air-gapped inference

AI is globally switchable with `AI_ENABLED` and provider selection remains tenant configuration.

Start the optional local service:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml \
  --profile local-ai up -d --wait ollama
```

The stack deliberately does **not** download a model at startup. For an air-gapped deployment, preload approved model artifacts/volumes from controlled offline media before the final isolation test. Configure a tenant `AIProviderConfig` with:

- `provider_type=ollama`;
- `base_url=http://ollama:11434`;
- an approved preloaded chat model in `model_name`;
- `configuration.embedding_model` set to an approved preloaded embedding-capable model;
- `allow_confidential=true` only after the local deployment is approved for that classification.

Then run a real generation + embedding smoke test:

```bash
docker compose --env-file .env -f docker-compose.pilot.yml \
  --profile local-ai exec -T backend \
  python manage.py pilot_readiness --ai-provider-id <AI_PROVIDER_CONFIG_UUID>
```

For the no-AI mode, set `AI_ENABLED=0`, recreate backend/worker, and verify AI calls are rejected while ordinary GRC functions remain usable. To switch from Ollama to vLLM/private/OpenAI-compatible, change the tenant provider configuration; domain modules must not change.

For the confidential-data acceptance test, disconnect/block internet egress after the approved model is loaded and repeat the smoke test.

## 6. Backup

Before the drill, create a controlled application marker (for example a clearly named test Evidence or Action) and record its timestamp.

Run:

```bash
bash scripts/pilot-backup.sh pilot-drill-001
```

The backup directory contains:

- `postgres.dump` — PostgreSQL custom-format dump;
- `objectstore.zip` — portable S3-level archive with per-object SHA-256 values;
- `config.env` — **secret-bearing** deployment configuration;
- Compose/source/image manifests;
- `SHA256SUMS`;
- `backup-observation.json`.

`backups/` is Git-ignored. Copy the completed directory to approved encrypted backup media separated from the application volumes. TLS private keys are intentionally not copied by the script; recover them through the approved PKI/key-recovery process.

After a successful or failed backup attempt, `pilot-backup.sh` also records a secret-safe operational signal in the application database. The admin operations page uses this signal to show backup outcome and freshness; it does **not** replace restore testing or measured RPO/RTO.\n\nAfter backup completion, create a second clearly named marker. This marker is expected **not** to exist after restoring the earlier recovery point.

## 7. Destructive restore drill

Use a clean/replacement pilot environment when possible. Restore requires explicit approval:

```bash
CONFIRM_RESTORE=YES RESTORE_CONFIG=YES PILOT_TLS=YES \
  bash scripts/pilot-restore.sh pilot-drill-001
```

If the drill also includes local AI and the restored database already contains the provider configuration:

```bash
CONFIRM_RESTORE=YES RESTORE_CONFIG=YES PILOT_TLS=YES PILOT_LOCAL_AI=YES \
AI_PROVIDER_ID=<AI_PROVIDER_CONFIG_UUID> \
  bash scripts/pilot-restore.sh pilot-drill-001
```

The restore script:

1. verifies `SHA256SUMS`;
2. requires explicit destructive confirmation;
3. stops application writers;
4. restores PostgreSQL with `pg_restore`;
5. restores the object bucket only with explicit replacement mode;
6. starts the application and waits for health;
7. runs `pilot_readiness`;
8. writes `restore-observation.json` with observed time from application stop to readiness.

After restore, manually prove:

- the pre-backup marker exists;
- the post-backup marker does not exist;
- at least one evidence file can be downloaded and its application SHA-256 still matches;
- login, secure-cookie and CSRF flows work through HTTPS;
- scheduled/background processing works;
- local AI generation/embedding works with internet egress disabled when local AI is in scope.

## 8. RPO / RTO measurement

Do not estimate these values in advance.

- **Observed RTO:** use `observed_rto_seconds` written by the restore script, then add any manual validation time required by the organization's definition of service recovery.
- **Observed RPO:** compare the timestamp/state of the controlled marker immediately before the backup with the restored state. Record the real recoverable cutoff and any data intentionally created after that cutoff.

## 9. Support evidence

For a low-risk support snapshot, run:

```bash
bash scripts/support-evidence.sh
```

The bundle includes service state, tool versions, pilot readiness status and
`operational-status.json`. It excludes application logs, customer records,
database/object-store payloads and secret-bearing environment values by design.

## 10. Acceptance evidence bundle

After the real drill, use `docs/PILOT_ACCEPTANCE_EVIDENCE.md` as the closure/evidence procedure. The collector `scripts/pilot-acceptance-evidence.py` reuses the readiness, backup/restore and AI tooling above and produces a low-risk PASS/FAIL/NOT_MEASURED/MANUAL_REQUIRED summary.

The evidence collector is **not** a replacement for the tests in this runbook. It cannot prove clean-host provenance, browser-authenticated cookie/CSRF behavior, network egress isolation, destructive marker behavior or RPO/RTO acceptance without explicit operator attestations.

Use the committed template only as a starting point and keep the populated copy in ignored runtime storage:

```bash
cp docs/PILOT_MANUAL_OBSERVATIONS.example.json runtime/pilot-manual-observations.json
chmod 600 runtime/pilot-manual-observations.json
```

A representative final collection command is:

```bash
python3 scripts/pilot-acceptance-evidence.py \
  --tls \
  --base-url https://grc-pilot.example.internal/ \
  --ai-provider-id <AI_PROVIDER_CONFIG_UUID> \
  --backup-observation backups/pilot-drill-001/backup-observation.json \
  --restore-observation backups/pilot-drill-001/restore-observation.json \
  --manual-observations runtime/pilot-manual-observations.json \
  --require-complete
```

Only the low-risk acceptance summary should normally be attached to Issue #7. Never attach `.env`, the backup directory, TLS private keys, raw customer Evidence, connector credentials, raw application logs or full AI adversarial responses/canaries to GitHub.

## Measured pilot observations

| Item | Actual result | Evidence / notes |
|---|---|---|
| Clean host / OS | NOT_MEASURED | Populate during target-host drill |
| Release commit | NOT_MEASURED | `acceptance-summary.json` / exact Git SHA |
| Core services healthy | NOT_MEASURED | `pilot_readiness` + collector summary |
| HTTPS / secure cookie / CSRF | NOT_MEASURED | TLS probe + operator attestation |
| Backup duration | NOT_MEASURED | `backup-observation.json` / sanitized bundle summary |
| Restore RTO | NOT_MEASURED | `restore-observation.json` + approved RTO attestation |
| Restore RPO | NOT_MEASURED | Controlled marker evidence + approved RPO attestation |
| Object evidence restored | NOT_MEASURED | Evidence id/checksum reference; do not attach payload |
| Local AI offline | NOT_MEASURED | Generation/embedding readiness + no-egress evidence reference |
| AI disable/provider switch | NOT_MEASURED | Operator attestation to tested configurations |
| Operational gaps | NOT_MEASURED | Convert unresolved items into tracked issues |

Issue #7 stays open until the real observations meet the acceptance criteria and `acceptance-summary.json` reports `ready_to_close_issue_7=true` after human review of the referenced evidence.
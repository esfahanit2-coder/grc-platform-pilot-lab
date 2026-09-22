# HA/DR and upgrade/rollback operations

This document is the implementation/runbook record for Issue #21. It deliberately separates behavior exercised by repository tooling from production HA assumptions that require target-environment validation.

## Validation boundary

### Exercised by repository tooling and CI

- a migration plan can be inspected before it is applied;
- a release transition fails closed when the pending Django plan contains a backward step or an operation Django marks irreversible;
- a pull request can rehearse the forward migration from its base commit to its head commit against disposable PostgreSQL 18 + pgvector;
- a pre-upgrade backup can quiesce application writers and record the deployed source commit, PostgreSQL major version, checksums and object-store archive metadata;
- restore refuses checksum failures, unsupported manifest schemas, PostgreSQL-major mismatches and unapproved cross-version paths;
- rollback validates the backup, switches the clean checkout to the exact source commit recorded in the pre-upgrade backup and invokes that release's restore implementation;
- an ancestor backup may be restored into a newer checkout only with explicit forward-compatible approval and another migration-safety audit.

### Reference architecture assumptions, not CI proof

The repository does **not** claim that CI proves:

- database replication, automatic leader election or split-brain prevention;
- object-storage replication durability;
- Redis/Sentinel/managed-cache failover behavior;
- load-balancer failover, DNS propagation or real certificate/key recovery;
- application capacity after a node loss;
- production RPO or RTO.

Those observations remain environment evidence. Real RPO/RTO and restore timing remain tied to Issue #7 and the target-host drill.

## 1. Supported deployment shapes

### Single-host pilot

The supported pilot remains `docker-compose.pilot.yml`: PostgreSQL, Redis, S3-compatible object storage, Django backend, Celery worker/beat, Next.js frontend and Nginx gateway on one host. It is intentionally simple and is **not** presented as highly available.

### Production-oriented HA reference topology

A production deployment should separate critical failure domains even when the exact HA products differ by organization:

1. **Ingress / TLS** — at least two ingress/load-balancer instances or an organization-provided HA load balancer. Keep certificate issuance and private-key recovery outside the application repository.
2. **Stateless application tier** — two or more backend/frontend instances distributed across hosts/failure domains. Do not run schema migration concurrently from every application replica; migration is a controlled release step.
3. **Worker tier** — multiple Celery workers may be distributed, while beat/scheduler leadership must remain singular or use an approved singleton/leader mechanism.
4. **PostgreSQL** — primary plus one or more replicas managed by an approved PostgreSQL HA/failover mechanism. The application must use the organization-approved writer endpoint; this repository does not implement database leader election.
5. **Object storage** — an approved replicated S3-compatible service or managed object store. Evidence objects and database metadata are both recovery-critical.
6. **Redis** — an approved HA Redis deployment when availability of broker/cache/throttle state matters. Redis is not the authoritative store for GRC records, but loss/failover can affect queued/background work and security throttle state.
7. **Backup target** — encrypted backup media/storage outside the application failure domain and outside the primary data volumes.

Do not place PostgreSQL primary/replica, all app replicas, object-store replicas and backup media on one physical failure domain and call the result HA.

## 2. Failure domains and recovery ordering

| Failure / dependency | Authoritative data concern | Recovery / failover order | Repository proof vs environment proof |
|---|---|---|---|
| Ingress node | No authoritative GRC data | Route to healthy ingress, then validate TLS and forwarded scheme | Reference assumption; real LB/DNS/TLS must be tested |
| Backend/frontend node | Stateless application process | Remove unhealthy node, restore replica, then readiness check | Container health/readiness exists; multi-node failover is environment proof |
| Celery worker | In-flight background work | Replace worker, inspect queued/retry state and audit results | Worker behavior is tested functionally; node-loss behavior is environment proof |
| Redis | Broker/cache/throttle state | Restore approved Redis service before workers; verify queue/throttle behavior | Pilot Redis persistence exists; HA failover is environment proof |
| PostgreSQL writer | Core transactional state | Promote/fail over through approved DB mechanism, point writer endpoint, verify consistency, then start writers | Backup/restore tooling exists; replication/election is environment proof |
| Object storage | Evidence object bytes | Restore/fail over object storage before exposing evidence workflows; validate object checksum against application metadata | Archive round-trip is tested; replicated-store failover is environment proof |
| Entire site/host | DB + evidence + config + runtime | Restore dependencies first, then DB/object data, migrations, app services, ingress, functional validation | Pilot restore path is executable; actual RPO/RTO is Issue #7 evidence |

### Recovery dependency order

For a cold recovery use this order unless the approved infrastructure design requires a stricter sequence:

1. network/DNS/private dependency reachability;
2. PostgreSQL, Redis and object storage;
3. restore PostgreSQL and evidence objects from one approved recovery set;
4. audit and apply only the migration plan appropriate to the checked-out application release;
5. backend;
6. workers and scheduler;
7. frontend;
8. ingress/TLS;
9. readiness plus business-level validation.

Do not expose application writers before database/object-store compatibility is established.

## 3. Migration safety contract

`python manage.py release_migration_plan` inspects the pending Django migration plan without applying it. It emits `grc-release-migration-plan-v1` JSON.

Use the fail-closed form for a release transition:

```bash
cd backend
python manage.py release_migration_plan --require-reversible
```

The command blocks when:

- the target plan unexpectedly requires a backward migration step; or
- a pending operation has `reversible = False` according to Django.

This does **not** mean production rollback should normally reverse schema migrations. The supported operational rollback is restoration of the quiesced pre-upgrade backup under the exact previous application commit. Reversibility is checked so that the release does not silently introduce an unacknowledged one-way schema transition.

If a future business requirement genuinely needs an irreversible migration, do not weaken this gate just to make CI green. Treat it as an explicit release-design change: document the one-way boundary, backup/restore recovery path, data-conversion semantics and approval in a dedicated change/issue before changing the gate.

## 4. Disposable migration rehearsal

Rehearse a known previous release to the current checkout:

```bash
bash scripts/migration-rehearsal.sh <previous-release-tag-or-commit>
```

The script:

1. resolves and validates the baseline as an ancestor of the current target;
2. creates a detached temporary worktree for the baseline;
3. starts disposable PostgreSQL 18 + pgvector on an isolated Docker network;
4. builds the baseline and target backend images;
5. applies the baseline migrations;
6. runs the target migration safety audit against that real baseline schema;
7. applies the target migrations;
8. confirms there are no remaining pending migrations and runs `manage.py check`;
9. writes machine-readable rehearsal observations;
10. removes temporary containers, network, images and worktree.

For pull requests, CI uses the PR base commit as the rehearsal baseline. This is a software migration proof, not a substitute for a representative-host performance or DR drill.

## 5. Backup compatibility contract

`scripts/pilot-backup.sh` writes `backup-manifest.json` with schema `grc-backup-manifest-v1`, including:

- backup name and timestamp;
- deployed source commit;
- optional release label;
- PostgreSQL `server_version_num` and major version;
- dump format;
- object-store archive schema version;
- whether application writers were quiesced;
- expected backup components.

`SHA256SUMS` covers the database dump, evidence archive, configuration snapshot, Compose metadata, image list, source commit and backup manifest.

For a release transition, backup creation uses a validated `BACKUP_SOURCE_COMMIT` because the Git checkout may already contain the target release while the still-running containers are the previous release. Operators must supply the actual deployed release ref to `pilot-upgrade.sh`; the tool cannot infer organizational deployment intent from Git history alone.

## 6. Upgrade procedure

Prerequisites:

- maintenance window and rollback owner approved;
- exact currently deployed Git ref known;
- target checkout has no tracked working-tree modifications;
- current application readiness passes;
- baseline ref is an ancestor of the target ref;
- approved backup storage has sufficient capacity.

Run from the **target** checkout:

```bash
CONFIRM_UPGRADE=YES \
  bash scripts/pilot-upgrade.sh <currently-deployed-ref> pre-upgrade-001
```

Set `PILOT_TLS=YES` and/or `PILOT_LOCAL_AI=YES` when those profiles are part of the deployment.

The upgrade path is intentionally fail closed:

1. validate current readiness and Compose configuration;
2. build target preflight images without replacing the running release images;
3. inspect the target migration delta against the live schema without applying it;
4. create a **quiesced** pre-upgrade DB + object-store rollback backup and leave application writers stopped;
5. build the exact target Compose images;
6. repeat the migration audit with the exact target service image;
7. apply migrations while writers remain stopped;
8. start the target release and wait for readiness;
9. write `upgrade-observation.json` and preserve the rollback backup.

If failure occurs before schema migration begins, the script restarts the existing stopped containers. If failure occurs after migration begins, writers remain stopped and the operator is directed to the backup-based rollback path.

Do not delete the pre-upgrade backup until the release observation window is formally closed.

## 7. Rollback procedure

Rollback uses the source commit recorded in the quiesced pre-upgrade backup and is intentionally destructive. Run the helper from the current/failed target checkout; do **not** manually switch to the old commit first because older releases may not contain the current rollback wrapper.

Prerequisites:

- the pre-upgrade backup is present and checksum-verifiable;
- the repository has no tracked working-tree changes;
- the backup source commit is available in the local Git object database;
- incident/change approval has authorized rollback.

Run:

```bash
CONFIRM_ROLLBACK=YES \
  bash scripts/pilot-rollback.sh pre-upgrade-001
```

The helper:

1. verifies `SHA256SUMS` before changing Git state;
2. validates the backup manifest and requires a release-consistent quiesced backup;
3. validates that the recorded source commit exists locally;
4. switches the clean checkout to that **exact** source commit in detached-HEAD mode when needed;
5. invokes `scripts/pilot-restore.sh` from that exact source release.

The currently running rollback wrapper remains in the active Bash process across the Git switch, while the restore implementation executed afterward comes from the release that created the application state being restored. The ignored `backups/` directory and `.env` remain outside tracked Git state.

After service recovery, record the rollback/incident evidence and deliberately return the repository to the organization's normal deployment branch/ref before the next release operation.

## 8. Forward-compatible disaster recovery

Normal release rollback restores the previous release under its exact source commit. A different case is restoring an **older** compatible backup into a newer application checkout during disaster recovery.

That is blocked by default. When deliberately approved, use:

```bash
CONFIRM_RESTORE=YES \
RESTORE_ALLOW_FORWARD_COMPATIBLE=YES \
  bash scripts/pilot-restore.sh <backup-name>
```

The restore proceeds only when:

- the backup was quiesced;
- the backup source commit is present locally and is an ancestor of current `HEAD`;
- PostgreSQL major versions match;
- pending migrations pass the reversible-plan audit.

A backup from a newer or divergent commit is rejected. PostgreSQL major-version migration is outside this helper and requires a separately approved PostgreSQL upgrade procedure.

## 9. DNS, TLS and HA operator decision points

Before enabling automated or manual infrastructure failover, define and test outside this repository:

- the canonical service hostname and DNS/LB failover mechanism;
- DNS TTL and expected client/cache behavior;
- health-check endpoint and failure threshold used by the load balancer;
- where TLS private keys live, how they are replicated/recovered and who can access them;
- PostgreSQL writer endpoint semantics and who/what may promote a replica;
- split-brain fencing for the selected PostgreSQL HA technology;
- object-store consistency/replication guarantees;
- Redis failover semantics and accepted queue-loss/duplication behavior;
- whether Celery tasks are safe to retry for each critical workflow;
- the human approval point for site failover and failback.

The application repository should consume stable service endpoints; it should not embed an unreviewed database/object-store leader-election implementation.

## 10. Evidence to retain per release transition

Retain at least:

- exact from/to Git SHAs;
- CI and release-gate result for the target SHA;
- migration rehearsal report;
- `backup-manifest.json` and `SHA256SUMS` for the pre-upgrade backup;
- `upgrade-migration-plan.json`;
- `upgrade-observation.json`;
- post-upgrade readiness evidence;
- rollback/incident evidence if rollback was invoked.

Production RPO/RTO values must come from a real host/site drill; do not derive them from CI or from this reference architecture.

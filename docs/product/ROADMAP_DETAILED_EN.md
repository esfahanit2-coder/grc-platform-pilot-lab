# GRC Platform — Detailed Roadmap (English)

This roadmap explains not only what is scheduled, but why each gate exists and what evidence is required before it is considered complete.

## Release targets

- `v0.9.0-pilot`: usable end-to-end pilot candidate with real GRC workflows and controlled operational proof.
- `v1.0.0-rc1`: release candidate after pre-v1 engineering, security and operational readiness gates.

## Gate 0 — Repository and CI normalization — COMPLETE

**Purpose:** make GitHub the reproducible source of truth before feature acceleration.

Completed outcomes include the canonical private repository, committed npm lockfile, backend/frontend CI, PostgreSQL 18 + pgvector migration from empty DB, full Django tests, Next.js production build, SAST, secret scan, container scan, SBOM generation and release gating.

**Done means:** a fresh commit cannot be merged/released while the core build/security/runtime gates fail.

## Gate 1 — Internal pilot foundation — SOFTWARE COMPLETE, REAL-HOST PROOF PENDING (#7)

**Purpose:** prove that the product can run as a sovereign on-premise system, not only inside development/CI.

Software already includes pilot compose, TLS gateway, local S3-compatible storage, optional local AI, readiness checks, backup/restore tooling and operational runbooks.

Remaining real-world proof:
- deploy on a clean pilot host;
- run real destructive backup/restore drill;
- measure observed RPO/RTO rather than inventing values;
- verify browser cookie/CSRF mode under real TLS;
- run local Ollama/vLLM with internet egress disabled.

**Done means:** another operator can deploy, restore and operate the pilot from documented artifacts with measured recovery evidence.

## Gate 2 — Content pilot — FOUNDATION COMPLETE, AUTHORIZED CONTENT PENDING (#5)

**Purpose:** prove the framework-as-content model using real legally usable content.

Completed:
- versioned content-pack/import model;
- licensing/provenance metadata;
- tenant-scoped restricted-content path;
- AFTA customer-provided conversion foundation;
- human approval path for mappings/crosswalks;
- internal example control baseline;
- SoA/RTP/audit/report outputs.

Remaining:
- authorized ISMS/ISO 27001 source material;
- documented software-use/redistribution rights where relevant;
- at least one human-approved real AFTA ↔ ISMS ↔ Internal/Common-Control mapping.

**Done means:** the product demonstrates real multi-framework reuse without violating content rights.

## Gate 3 — Connector pilot — IMPLEMENTATION/UI COMPLETE, LIVE PROOF PENDING (#6)

**Purpose:** prove that infrastructure facts can become auditable reusable Evidence without bypassing human judgment.

Implemented providers:
- AD/LDAP;
- FortiGate;
- Veeam;
- Tenable/Nessus.

Implemented boundaries include read-only collection, secret references, SSRF restrictions, target validation, normalized provider datasets, Evidence provenance/hash, failure diagnostics, human-review metadata and Connector Operations UI with health/sync/run history.

Remaining:
- run authorized live health/sync against available internal systems;
- create reusable Evidence from at least three real connector types;
- record representative failures and confirm diagnosability.

**Done means:** live internal systems prove the same contracts already exercised by offline/synthetic tests.

## Gate 4 — v1.0 Release Candidate hardening

### #19 Operational UI — COMPLETE

Production-facing fabricated dashboard values were removed. Management metrics are live tenant-scoped data. Connector Operations UI exists with explicit loading/empty/error states and safe operational metadata.

### #20 Performance/load readiness — COMPLETE (software validation)

Repeatable pre-RC performance validation now includes N+1/query-amplification regression coverage, a dependency-light HTTP load harness, machine-readable latency/error/throughput output, CI self-test and documented provisional engineering budgets. Those budgets are not contractual SLOs or production-capacity claims; representative-host measurement remains operational evidence.

### #21 HA/DR and upgrade/rollback — COMPLETE (reference + software tooling)

The repository now provides:
- a documented HA/DR reference topology and explicit failure domains;
- DB/object-store/Redis/application recovery ordering and operator decision points;
- machine-readable Django migration-plan safety analysis;
- disposable PostgreSQL 18 migration rehearsal from release baseline to target;
- versioned/quiesced pre-upgrade backup manifests with source-commit and PostgreSQL compatibility checks;
- fail-closed upgrade sequencing;
- exact-source-commit backup-based rollback;
- explicitly gated ancestor-to-current disaster-recovery restore;
- clear separation between repository-tested behavior and real infrastructure failover/RPO/RTO evidence.

Real replication/failover behavior and measured RPO/RTO still belong to target-environment validation under #7; they are not claimed by CI.

### #22 Offline release bundle and support — COMPLETE (software/tooling contract)

The repository now provides:
- deterministic release manifests with exact payload SHA-256/size verification and extra/missing-file rejection;
- detached OpenSSL signing with the production private key explicitly outside Git/CI and an out-of-band trusted public-key boundary;
- exact backend/frontend plus pinned infrastructure image archives and Docker image-ID verification;
- an exact Git source bundle, CycloneDX SBOMs, migration inventory and public configuration schema;
- digest references to retained security reports without embedding raw secret-scan output into distribution media;
- air-gapped install/update tooling that verifies before mutation and uses preloaded images with `--no-build`;
- offline-aware fail-closed upgrade and release-version-aware backup rollback integration;
- reference-only local-AI model metadata so third-party model weights are not redistributed by this release process;
- a consolidated offline release/operator support handbook and a secret-minimized support-evidence collector;
- CI/Release Gate self-tests for deterministic manifest output, ephemeral signing, verification and tamper rejection.

Actual production signing-key custody/HSM operations and real disconnected-host installation observations remain organization/environment evidence; the repository does not claim those from CI.

### #8 Independent security validation — AUTOMATED HARDENING COMPLETE, EXTERNAL PROOF PENDING

Automated hardening already covers auth throttling, TOTP replay resistance, CSRF negative paths, cross-tenant IDOR, Evidence quarantine/fail-closed download, export audit, renderer SSRF/local-file boundaries, RAG untrusted-context guardrails, SAST, secret scanning, container scanning and SBOMs.

Remaining:
- independent penetration test;
- real malware scanning workflow or formally accepted operational substitute;
- adversarial testing of configured real AI providers;
- final security sign-off and remediation closure.

## Post-v1 product expansion

Post-v1 priorities discussed and retained:
- TPRM/vendor portal;
- BCM/BIA and continuity workflows;
- incident management;
- continuous control monitoring;
- additional connector packs;
- FAIR/quantitative risk/Monte Carlo;
- advanced regulated document/report templates;
- AI-governance content such as ISO 42001 where authorized;
- digital-transformation maturity packs;
- mobile/PWA approvals.

## Roadmap discipline

A gate is not complete merely because code exists. If acceptance requires a real host, real connector, licensed content or independent validation, the issue stays open until that evidence exists. Conversely, unavailable customer infrastructure must not block unrelated software engineering work that can be completed and tested offline.

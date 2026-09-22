# Customer-Ready v1 Product Audit

Status baseline: `main@cf835537e3662bc320b4b20bc44b1b089831d864`

Related umbrella: #44

## Purpose

This document is the durable engineering snapshot for one question:

> What still separates the current repository from a customer-ready v1 release?

It distinguishes **repository-side productization** from **real deployment / legal / security acceptance**. CI success is necessary evidence, but it is not a substitute for a licensed content source, a real connector target, a destructive recovery drill, an independent penetration test, or customer UAT.

## Current executive assessment

The repository-side customer-productization program is now materially complete for the P0 areas identified in #44.

The platform should still be described as **Pilot Candidate / pre-RC**, not as a completed production release, because external acceptance issues remain open.

### Repository-side P0 status

| Area | Current state | Evidence / note |
|---|---|---|
| Customer onboarding/setup | Productized | First-customer setup, organization/security/readiness flows are available without normal-operation Django shell shortcuts. |
| Evidence Workspace | Productized | Upload/provenance/hash/quarantine/scan/linkage/reuse/freshness customer flows are implemented. |
| Work Center / My Tasks | Productized | Operational inbox aggregates authoritative source records instead of creating a second business-state model. |
| Customer administration | Productized | User lifecycle, role/scope administration, MFA/security-sensitive actions and auditability are available through product UI. |
| Controlled documents | Productized | #54 completed document/version/submit/review/approve/history UX. |
| Workflow execution | Productized | #56 completed assignments, permission-aware transitions, history and actionable workflow execution UX. |
| Reporting Center | Productized | #58 completed SoA/RTP/Audit/Findings/Actions/Executive preview/export flows with scoped server-side data. |
| Initial customer data exchange | Productized | #60 completed CSV/XLSX templates, scoped exports, signed dry-run validation and atomic imports. |
| Operational baseline | Productized | #62 completed runtime health, queue/worker heartbeat, backup freshness and secret-safe support status. |
| Core register UX | Productized | #64 removed remaining Asset prompt/first-record shortcuts and aligned Assets/Actions/Audits/Findings/navigation UX. |
| Executive dashboard | Repository-side parity complete | PR #43 delivered live tenant-scoped heatmap, framework summaries, assessment progress, top risks/actions/deadlines and executive panels. #42 remains open only for real running-Pilot visual evidence. |
| Enterprise SSO | Conditional | Local password + MFA is the supported baseline. See ADR-008. Implement only when the first customer identifies an actual IdP/protocol requirement. |

## What is now strong

### GRC domain and traceability

The platform retains the intended common-control architecture:

`Framework -> Version -> Requirement <-> Common Control -> Control Implementation -> Evidence -> Test`

`Asset/Process -> Risk -> Evaluation -> Treatment -> Action -> RTP`

Assessment, finding/CAPA, internal audit, controlled documents, workflow, reporting and AI/RAG capabilities operate around that core.

### Customer-facing execution

The previous mismatch between a mature backend and prototype customer UX has been substantially reduced.

Primary workflows now have productized selectors/forms, loading/error/empty states, scope-aware actions and auditable mutations. Browser prompt/first-record shortcuts should no longer be treated as an accepted production interaction pattern.

### Security and release discipline

Repository controls include:

- tenant and organization-scope RBAC;
- TOTP MFA and hardened authentication/session paths;
- tamper-evident audit integrity tooling;
- Evidence quarantine and malware-scanner boundary;
- connector SSRF/credential controls;
- permission-safe RAG / AI boundaries;
- human-governed AI acceptance;
- migration checks and PR-base migration rehearsal;
- dependency/SAST/secret/container-image scans;
- SBOM and release-gate enforcement;
- offline/on-prem deployment and support tooling.

Every productization merge remains subject to exact-head CI + Release Gate and one post-merge CI verification.

### Deployment and support model

The Pilot composition supports PostgreSQL + pgvector, Redis, S3-compatible object storage, Django, Celery worker/beat, Next.js, TLS gateway and optional local AI.

Backup/restore, operational status, support evidence, signed offline install/update, operator-safe bootstrap, upgrade/rollback and machine-readable datacenter verification are now packaged through #73. Post-merge CI is green on `main@cf835537e3662bc320b4b20bc44b1b089831d864`. Real target-host observations remain deliberately unmeasured until the authorized drill.

## Remaining internal product decision

### Enterprise authentication / SSO

No speculative SSO implementation should be added merely to increase feature count.

ADR-008 records the current decision:

- password + MFA remains the supported baseline authentication path;
- the AD/LDAP connector is evidence collection, not interactive SSO;
- identify the first customer's IdP and protocol before implementation;
- prefer OIDC Authorization Code + PKCE when supported;
- implement SAML only when required by the target IdP/contract;
- external authentication must never auto-grant tenant roles or organization scopes;
- controlled break-glass local administration remains required.

If the first customer does not require SSO, SSO is not a v1 release blocker for that deployment.

## Remaining external / environment acceptance

These are not repository feature gaps and must not be fake-closed from CI.

### #5 — Authorized AFTA / ISMS content

Still required:

- legally authorized source material;
- licensing/provenance record;
- approved mappings/crosswalks;
- real content-pack import evidence.

No restricted standards text should be committed without authorization.

### #6 — Live connector validation

Software contracts and security boundaries for AD/LDAP, FortiGate, Veeam and Tenable/Nessus are already prepared.

Still required:

- authorized representative endpoints;
- least-privilege live credentials;
- successful health/sync execution;
- real reusable Evidence from at least three connector types;
- human-review linkage validation.

### #7 — Clean-host Pilot and recovery evidence

Repository-side deployment tooling is ready.

Still required on a controlled real host:

- clean install of an exact release SHA;
- approved TLS;
- production cookie/CSRF behavior;
- destructive DB/object-store restore;
- measured RPO/RTO;
- worker/beat/queue/backup observations;
- local-AI/no-AI/provider-switch validation as applicable;
- low-risk acceptance evidence bundle.

### #8 — Independent security acceptance

Repository-side negative-path hardening and pentest preparation are already implemented.

Still required:

- authorized real malware-scanner validation;
- deployment-level audit-integrity/storage evidence as required;
- independent penetration test completed or formally scheduled under release policy;
- real-model adversarial testing when AI is enabled;
- triage/retest evidence;
- no unresolved Critical/High release blocker;
- named final security/release sign-off.

### #40 — Server-enforced branch protection

Still plan/platform dependent. Until available, exact-head gate checks and explicit merge discipline remain compensating controls.

### #42 — Real visual Pilot evidence

Repository-side dashboard parity is already merged.

Still required:

- genuine screenshot from a running Pilot deployment;
- comparison against the approved Persian dashboard mockup direction;
- no mock/generated screenshot as acceptance evidence.

## Final acceptance control

Issue #74 is the final release/UAT orchestration layer. It must aggregate—not replace—the real evidence from #5, #6, #7, #8 and #42 plus customer/operator UAT. `docs/FINAL_RELEASE_ACCEPTANCE.md` defines the fail-closed promotion process; missing external evidence remains BLOCKED and no RC tag is promoted from repository CI alone.

## Recommended next execution sequence

Do not start another broad feature wave.

1. **Run #7 clean-host Pilot** on the exact approved `main` SHA.
2. During that same Pilot session, capture the genuine dashboard evidence required by **#42**.
3. Execute authorized live connector validation for **#6** when representative targets are available.
4. Import the first legally authorized content pack for **#5** when source rights/material are available.
5. Execute / schedule the independent security work required by **#8** and close findings through retest.
6. Resolve #40 when repository plan/policy permits.
7. Run final customer UAT against the exact candidate release.
8. Implement SSO only if the target customer requirement activates ADR-008.

## Customer-Ready v1 exit test

A candidate release is customer-ready only when a fresh target environment can prove, without developer-only shortcuts:

1. controlled installation from release artifacts;
2. TLS, storage, database, workers, backup and support readiness;
3. tenant/admin onboarding and organization/user/scope setup;
4. authorized framework/content import;
5. asset/risk/evaluation/treatment workflows;
6. control implementation + reusable Evidence;
7. Assessment -> Evidence -> Finding -> CAPA/Action -> review/close;
8. internal audit, control testing and controlled-document approval;
9. workflow assignment/transition execution;
10. formal report generation;
11. Work Center assignments/approvals;
12. tenant/scope enforcement and audit trail;
13. customer import/export;
14. backup/restore/upgrade/support drill;
15. required connectors, local AI and SSO according to contracted scope;
16. independent security acceptance;
17. customer UAT.

Until applicable external acceptance is complete, the correct release description remains **Pilot Candidate / pre-RC**.

# Roadmap

## Current state: Pilot Candidate / pre-RC hardening

Implemented foundations include multi-tenancy, scoped RBAC, MFA, framework engine, common controls, asset/risk management, assessments, evidence, findings/CAPA, audit/workpapers, control testing, documents/report factory, workflows, notifications, AI gateway, permission-safe RAG, read-only pilot connectors, a live operational dashboard and Connector Operations UI.

For the rationale, Definition of Done and Persian/English explanations behind these gates, see `docs/product/ROADMAP_DETAILED_EN.md` and `docs/product/ROADMAP_DETAILED_FA.md`.

## Gate 0 — Repository and CI normalization — complete

- [x] Private canonical GitHub repository.
- [x] Real committed `frontend/package-lock.json`.
- [x] Backend/frontend CI on `main`.
- [x] PostgreSQL 18 + pgvector migrations from an empty database.
- [x] Complete Django suite and Next.js production build.
- [x] Tagged/manual release process with SAST, secret scan, container scan and SBOM gates.

## Gate 1 — Internal pilot — software foundation complete, real-host proof pending

- [ ] Deploy `docker-compose.pilot.yml` on a clean pilot host. (#7)
- [x] Create/rehearse tenant and organization hierarchy through the Golden E2E scenario.
- [x] Run Golden E2E scenario end-to-end on PostgreSQL 18 + pgvector. (#4)
- [ ] Execute destructive backup/restore drill and measure RPO/RTO on the real host. (#7)
- [ ] Validate browser cookie/CSRF mode under real TLS. (#7)
- [ ] Validate local Ollama/vLLM path with internet egress disabled. (#7)

## Gate 2 — Content pilot — AFTA supplied, ISMS/legal completion pending

- [x] Build legally safe customer-provided AFTA conversion/provenance workflow foundation. (#5)
- [x] Build tenant-scoped restricted-framework import and auditable mapping approval path. (#5)
- [ ] Supply/import authorized ISMS source material and document applicable rights. (#5)
- [ ] Approve at least one real AFTA/ISMS/internal Common Control mapping with human review. (#5)
- [x] Produce SoA, RTP and audit/report outputs in the Golden E2E engine.

## Gate 3 — Connector pilot — implementation/UI complete, live proof pending

- [x] AD/LDAP provider contract, normalization and security boundaries.
- [x] FortiGate provider contract, normalization and security boundaries.
- [x] Veeam provider contract, normalization and security boundaries.
- [x] Tenable/Nessus provider contract, normalization and security boundaries.
- [x] Secret-reference, SSRF, read-only Evidence provenance and human-review guardrails.
- [x] Add production operational dashboard and connector health/sync history UI. (#19)
- [ ] Run authorized live health/sync and create real Evidence from at least three connector types. (#6)

## Gate 4 — v1.0 Release Candidate

- [x] Remove production-facing demo dashboard values and complete the first critical operational UI batch. (#19)
- [x] Establish repeatable performance/load validation and pilot engineering budgets. (#20)
- [ ] Complete/schedule independent penetration testing and final security sign-off. (#8)
- [x] Publish HA/DR reference topology and rehearse upgrade/rollback behavior. (#21)
- [x] Build deterministic signed/verifiable offline release bundle process and support handbook. (#22)
- [ ] Finish actual clean-host operational proof. (#7)
- [ ] Finish authorized content/crosswalk proof. (#5)
- [ ] Finish live connector proof. (#6)

## Post-v1 priorities

- TPRM/vendor portal.
- BCM/BIA.
- Incident management.
- Continuous control monitoring.
- More connector packs.
- Quantitative risk/FAIR/Monte Carlo.
- Advanced document generation and regulated templates.
- AI governance pack / ISO 42001.
- Digital-transformation maturity pack.
- Mobile/PWA approval experience.

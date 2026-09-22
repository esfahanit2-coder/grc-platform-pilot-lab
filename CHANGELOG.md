# Changelog

This project follows semantic versioning once tagged releases begin.

## Unreleased — Pilot Candidate

### Added
- Multi-tenant foundation and organization-scoped RBAC.
- TOTP MFA, tenant security settings, shared auth throttling and replay-resistant MFA verification.
- Framework/version/requirement engine with import/export, translations, version locking and auditable crosswalk approval.
- Common control library and organization-specific implementations.
- Asset register, configurable risk methodology, historical evaluations, treatments and RTP.
- Compliance assessments, reusable evidence, findings and CAPA.
- Internal audit, workpapers, control testing and document approval/versioning.
- SoA, RTP and audit/report generation with controlled export auditing and restricted PDF resource fetching.
- AI provider abstraction, local AI support, human-reviewed AI suggestions, pgvector semantic/hybrid RAG and untrusted-evidence prompt framing.
- Generic workflows, notifications and production cookie/CSRF hardening.
- Read-only AD/LDAP, Tenable/Nessus, Veeam and FortiGate connectors with normalized provider contracts, provenance and offline fixtures.
- Golden pilot E2E test on PostgreSQL 18 + pgvector.
- Reusable runtime/release gates with npm/pip dependency audit, Bandit, secret scanning, Trivy image scans and CycloneDX SBOMs.
- Pilot deployment foundation with TLS override, S3-compatible local object storage, optional Ollama profile, backup/restore tooling and readiness probes.
- Pre-v1 security negative-path hardening for tenant IDOR, evidence quarantine, connector boundaries, exports and RAG.

### Changed
- Frontend dependency installation is reproducible through the committed npm lockfile and `npm ci --ignore-scripts`.
- Connector Evidence explicitly remains read-only/advisory and cannot autonomously mark controls effective or requirements compliant.
- Remaining release blockers are tracked by real-world validation Issues #5-#8 and pre-RC engineering Issues #19-#22 rather than already-completed bootstrap work.

### Pending real-world proof
- Authorized ISMS/content-rights completion and final AFTA/ISMS/internal human-approved crosswalk.
- Live internal connector validation.
- Clean-host install, backup/restore, RPO/RTO and no-egress local-AI drill.
- Independent penetration test, real malware-scanning workflow and security sign-off.

# Release blockers

The repository remains a **Pilot Candidate / pre-RC hardening** build. Repository CI now proves the software/runtime preparation described below; the remaining blockers depend on authorized content, real infrastructure, a target deployment, independent review, organization-approved production configuration, or repository administration.

## Cleared by repository/runtime gates

- `frontend/package-lock.json` is committed and frontend builds use `npm ci --ignore-scripts`.
- PostgreSQL 18 + pgvector migrations run from an empty database in CI.
- Full Django tests, Golden E2E and connector contract tests pass in the reusable runtime gate.
- Next.js typecheck, lint and production build pass.
- Dependency audit, Bandit high-severity SAST, repository secret scan, backend/frontend Trivy HIGH/CRITICAL image scans and CycloneDX SBOM generation are enforced by the release gate.
- Release composition rejects mutable `:latest` application image tags.
- Deterministic negative-path tests cover key tenant/authorization, MFA replay, CSRF, IDOR, evidence quarantine, report-fetch and RAG boundaries.
- Operational dashboard and connector operations UI preparation is complete. (#19)
- Repeatable performance/load validation and pilot engineering budgets are implemented. (#20)
- HA/DR reference topology plus upgrade/rollback rehearsal tooling is implemented. (#21)
- Deterministic signed/verifiable offline release tooling and the support handbook are implemented. (#22)
- The clean-host pilot now has a fail-closed acceptance-evidence collector and operator-attestation flow; this prepares the real drill but does not replace it. (#36, related to #7/#8)

## Remaining before v1.0 RC / production rollout

1. **Authorized content (#5):** supply/import authorized ISMS source material, document rights/provenance, and approve at least one real AFTA/ISMS/internal Common Control mapping without unauthorized redistribution.
2. **Live connector proof (#6):** run authorized health/sync against representative AD/LDAP, FortiGate, Veeam and Tenable/Nessus systems; at least three connector types must create real reusable Evidence.
3. **Clean-host operations proof (#7):** execute clean install on the target host, validate real TLS/cookie/CSRF behavior, perform destructive backup/restore, measure actual RPO/RTO, prove monitoring/health, and validate no-egress local AI plus disable/provider-switch behavior.
4. **Security validation (#8):** complete or formally schedule independent penetration testing, validate the real malware-scanner workflow and relevant immutable/WORM audit-storage deployment controls, complete real-model AI human review, and document final named security sign-off.
5. **Target-environment Django deployment checks:** the datacenter verifier now executes `python manage.py check --deploy` against the running backend and externally probes the real HTTPS live/ready endpoints. This blocker is cleared only when those checks pass on the actual approved production/pilot environment; repository CI cannot substitute for that target-host execution.
6. **Final immutable deployment manifest:** pin production infrastructure/application images to organization-approved versions or immutable digests. The repository can enforce safe manifest rules, but it cannot invent the organization-approved production digests.
7. **Repository governance (#40):** protect `main` with an active branch protection rule or repository ruleset that requires pull-request flow and the applicable CI/Release Gate checks, and blocks unsafe direct/force updates according to policy. The connected GitHub App does not have repository Administration write access to configure this control.

## What must not be inferred from CI

Green CI and Release Gate do **not** prove real RPO/RTO, clean-host behavior, certificate/private-key handling, air-gapped model operation, live connector access, malware-signature operations, external penetration-test results, legally authorized standards content, final production image approval, or repository administration policy enforcement.

## Content/legal boundary

Do not bundle proprietary ISO/COBIT/AFTA text unless the distribution/use license explicitly permits embedding that content in the product. Customer-provided restricted content remains tenant-scoped unless broader rights are documented.

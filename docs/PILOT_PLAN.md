# Pilot plan

## Pilot objective
Prove the platform on one organization and one business unit with an original security/ISMS baseline, without distributing copyrighted ISO/COBIT/AFTA text. Licensed/customer-provided frameworks can be imported and cross-mapped during the pilot.

## Entry gates
- PostgreSQL migrations pass on pgvector PostgreSQL 18.
- Backend full tests pass.
- Golden pilot scenario passes.
- Frontend lint/build pass.
- Release lockfile gate passes before a tagged release.
- `python manage.py check --deploy` has no unresolved production-critical findings.

## Pilot scenario
1. Create tenant and organization.
2. Import `pilot-isms-security-baseline.json`.
3. Create common controls for IAM, backup, logging and vulnerability management.
4. Register key assets.
5. Perform 5x5 risk assessment.
6. Map controls to the pilot framework and any licensed/customer-provided framework.
7. Perform compliance assessment.
8. Collect manual and connector-produced evidence.
9. Create finding/CAPA.
10. Produce RTP/SoA/audit outputs and executive dashboard.
11. Exercise AI with Local AI where confidential data is involved.

## First connector pilots
- AD: account inventory / disabled-account summary.
- FortiGate: approved read-only `/api/v2/` paths using a least-privilege REST API administrator.
- Veeam: backup inventory/session evidence through Enterprise Manager.
- Tenable: scan inventory and last-status metadata.

## Exit criteria
- No cross-tenant or cross-scope access finding.
- 100% golden E2E pass in CI.
- At least three evidence objects collected automatically from connectors.
- A full assessment with RTP and SoA can be completed without developer intervention.
- AI can be disabled, run locally, or changed by provider configuration without domain-code changes.

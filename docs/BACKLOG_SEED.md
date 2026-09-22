# Initial Backlog Seed

The following work items should exist as GitHub Issues and gate the first pilot/release cycle:

1. Import the complete Pilot Candidate source tree into `import/pilot-candidate` and merge after review.
2. Generate and commit `frontend/package-lock.json` from a trusted connected environment.
3. Add/enable executable GitHub Actions CI and release gate matching `docs/CI_DESIGN.md`.
4. Prove clean PostgreSQL 18 + pgvector migrations and full backend test suite.
5. Prove frontend lint/type/build and npm audit using the committed lockfile.
6. Run Golden E2E pilot scenario from tenant creation through RTP/SoA/CAPA.
7. Build first legally authorized AFTA/internal-security content pack and mapping set.
8. Run read-only pilot connectors for AD, FortiGate, Veeam and Tenable with least privilege.
9. Deploy pilot stack on a clean host and prove backup/restore, TLS, cookie/CSRF security and local AI.
10. Execute pre-v1 security test focused on tenant/scope isolation, IDOR, upload, CSRF, SSRF and privilege escalation.

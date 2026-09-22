# Pre-RC Product Completeness Audit

Status: active

This audit tracks software work that can be completed before the remaining environment-dependent validation in Issues #5-#8.

## Already proven

- Reproducible frontend lockfile and `npm ci`.
- PostgreSQL 18 + pgvector migrations and full Django test suite in CI.
- Golden GRC end-to-end scenario.
- Tagged/manual runtime and security release gates with dependency audit, Bandit, secret scanning, Trivy image scanning and CycloneDX SBOMs.
- Offline provider contracts and security boundaries for AD/LDAP, FortiGate, Veeam and Tenable/Nessus.
- Pilot compose foundation with S3-compatible object storage, TLS override, backup/restore tooling and optional local AI.
- Deterministic pre-v1 negative-path security hardening.

## Environment-dependent validation still open

- #5: authorized ISMS source / legal usage confirmation and final human-approved AFTA/ISMS/internal crosswalk.
- #6: live connector validation against authorized internal systems.
- #7: clean-host install, destructive restore drill, measured RPO/RTO and no-egress local-AI proof.
- #8: independent penetration test, real malware-scanner integration/deployment validation and security sign-off.

## Software work still actionable before those dependencies

### Track A — Operational UI
- Remove production-facing demo KPIs/profile content from the dashboard.
- Bind the main dashboard to tenant-scoped management metrics.
- Add Connector Operations page with configuration visibility, health status, sync trigger and run history.
- Keep connector errors/provenance visible without exposing secret values.

### Track B — Performance/load readiness
- Establish repeatable API load/smoke scenarios for high-value read/write paths.
- Define initial response-time/error-rate budgets as pilot targets, not production claims.
- Capture query-count or obvious N+1 regressions for key endpoints where practical.

### Track C — HA/DR and upgrade/rollback
- Document supported single-host pilot and production-oriented HA topology.
- Add migration upgrade/rollback rehearsal tooling and release compatibility checklist.
- Define DB/object-store/config restore ordering and failover assumptions.

### Track D — Offline release and support
- Build a versioned offline release manifest/bundle process with checksums/SBOM references.
- Add verification/install/rollback instructions for disconnected environments.
- Consolidate operator/support troubleshooting guidance.

No item in this document should be treated as proof of an environment-dependent acceptance criterion until the corresponding real-world drill is executed.

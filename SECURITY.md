# Security Policy

## Product security principles

GRC Platform is intended to hold sensitive governance, audit, risk and evidence data. Security controls are therefore part of the product architecture rather than optional add-ons.

### Core principles

- Tenant isolation is enforced server-side.
- Organization-scope authorization is enforced server-side.
- Production browser sessions should use HttpOnly secure cookies plus CSRF protection.
- Secrets must not be committed or stored in plaintext application records.
- Uploaded evidence requires MIME/size validation, SHA-256 metadata and a deployable malware-scanner adapter.
- Security-relevant changes must be audit logged.
- AI retrieval is permission-filtered before semantic search.
- AI-generated consequential values require human approval.
- Connectors are evidence collectors, not autonomous compliance decision-makers.

## Supported deployment security

Production deployments should enable TLS termination, HSTS, CSP/security headers, rotated secrets, encrypted backups, dependency scanning and auditable release artifacts. Air-gapped deployments must use approved offline images/models and signed update bundles.

## Vulnerability reporting

Until a dedicated security mailbox/process is established, report suspected vulnerabilities privately to the repository owners and do not create a public GitHub issue containing exploitable details, credentials or customer data.

## Security gates before v1.0

- Complete runtime CI against PostgreSQL 18.
- Generate and commit npm lockfile.
- SAST/dependency/container scanning.
- SBOM generation.
- IDOR, tenant-isolation, RBAC-bypass and privilege-escalation test suite.
- File upload and malicious-content tests.
- CSRF/XSS/injection/brute-force tests.
- Backup/restore validation.
- External penetration test before production rollout.

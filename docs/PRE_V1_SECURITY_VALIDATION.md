# Pre-v1 Security Validation Register

Status: **IN PROGRESS — REPOSITORY PREPARATION ADVANCED, EXTERNAL ACCEPTANCE PENDING**  
Issue: #8  
Repository-preparation issue: #34  
Target: v1.0.0-rc1  
Last updated: 2026-09-16

This register separates controls that can be verified from the repository/CI from evidence that requires a real deployment, an approved malware scanner, the actual pilot AI model, or an independent penetration tester. A control is never marked complete merely because a mock or synthetic test exists.

## Current repository baseline

The current `main` baseline includes the merged pre-v1 negative-path hardening, fail-closed Evidence malware-scanning integration boundary, tamper-evident Audit Integrity chain/verifier, release SAST/secret/container gates, migration rehearsal, and supporting operational documentation.

Latest verified baseline before this preparation branch:

- merge commit: `fcf370b38f8100320afd738cfa6fe4ca60c39650`;
- post-merge CI #134: **SUCCESS**;
- the exact-head Release Gate for PR #33: **SUCCESS**;
- Issue #31 (repository-side Audit Integrity): **COMPLETED**.

Issue #8 remains open because repository CI cannot prove an independent pentest, a real malware-scanner deployment, real-model adversarial behavior, deployment-level immutable/WORM controls, or final security approval.

## Automated validation scope

The repository suite covers:

- tenant isolation and direct cross-tenant object-ID access;
- organization-scoped RBAC boundaries and privilege checks;
- public authentication throttling;
- MFA challenge flows and atomic TOTP replay resistance;
- cookie authentication, refresh behavior and CSRF negative paths;
- evidence upload active-content rejection, quarantine and fail-closed malware-clearance download gating;
- connector SSRF, redirect, TLS and secret-handling boundaries;
- RAG organization scope, classification controls and explicit untrusted-context framing;
- RAG non-disclosure instructions for hidden prompts, security canaries, credentials and secrets;
- sandboxed report rendering with external/local resource fetch disabled;
- sensitive document/report export audit events;
- append-only HMAC audit chaining, historical sealing, tamper/gap/head verification and actor `SET_NULL` integrity;
- release SAST, secret scan, HIGH/CRITICAL container vulnerability gates and SBOM generation;
- migration planning/rehearsal and post-merge CI.

Issue #34 adds a real-provider adversarial AI harness. Its automatic checks detect synthetic-canary leakage and execution failure, but **human review remains mandatory** and mock-provider output is rejected as production acceptance evidence.

## Finding / remediation register

| ID | Finding / acceptance gap | Severity | Owner | Due | Status | Retest / evidence |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-001 | Public login/MFA/refresh endpoints lacked dedicated throttles | High | Backend/Security | 2026-09-30 | REMEDIATED | Negative-path suite merged; current baseline CI #134 green |
| SEC-002 | Accepted TOTP could be replayed during its validity window | High | Backend/Security | 2026-09-30 | REMEDIATED | Atomic time-step consumption regression coverage; current baseline CI #134 green |
| SEC-003 | Report templates could attempt network/local URL fetches | High | Backend/Security | 2026-09-30 | REMEDIATED | Renderer SSRF/local-file blocking regression coverage; current baseline CI #134 green |
| SEC-004 | Evidence download previously lacked fail-closed malware clearance | High (engineering finding) | Backend/Security | 2026-09-30 | REPOSITORY REMEDIATED / OPERATIONAL VALIDATION OPEN | Quarantine + scanner integration merged; authorized real scanner deployment/test still required |
| SEC-005 | Sensitive document/report exports were not consistently audited | Medium | Backend | 2026-09-30 | REMEDIATED | Export audit coverage merged; current baseline CI #134 green |
| SEC-006 | Retrieved RAG text was blended without an explicit untrusted-evidence boundary | Medium | AI/Security | 2026-09-30 | REPOSITORY REMEDIATED / REAL-MODEL VALIDATION OPEN | Framing regression coverage merged; Issue #34 adds real-provider adversarial evidence harness |
| SEC-007 | Independent penetration test has not been completed or formally scheduled | Release blocker | Security/Release owner | Before v1.0.0-rc1 production approval | OPEN | Independent external evidence required |
| SEC-008 | Deployment-level immutable/WORM or externally protected audit checkpoint has not been independently validated | Medium / deployment control | Security/Operations | Before production rollout | OPEN | App-level HMAC chain/verifier is complete; deployment control evidence still required |
| SEC-009 | Actual pilot AI model/version has not completed adversarial human-reviewed evaluation | Release evidence | AI/Security | Before AI-enabled production approval | OPEN | Run `evaluate_ai_security` against the real provider and attach reviewed JSON evidence |
| SEC-010 | Final security sign-off has not been issued | Release blocker | Security/Release owner | Before production rollout | OPEN | Blocked by SEC-004 operational evidence, SEC-007, SEC-008, SEC-009 and any pentest findings |

Severity above is an engineering/release triage classification. Independent penetration-test findings retain the assessor's own severity and must not be silently downgraded to match this table.

## Evidence malware-scanning boundary

New uploads are forced into a non-clean state and client-supplied clean claims are not trusted. Active/executable formats are rejected before object-storage acceptance. Production download remains fail-closed until the server-owned scanning path marks the exact stored object clean.

Repository integration is not equivalent to scanner acceptance. Production evidence must identify the authorized scanner product/service, deployment boundary, version/signatures, a known-clean test, a safe industry-standard test artifact where organizational policy permits it, failure/timeout behavior, quarantine behavior, and the exact release/environment tested.

## Audit-integrity boundary

Repository-side tamper evidence is implemented and documented in `docs/AUDIT_INTEGRITY.md`. It provides per-scope HMAC chaining, historical sealing, immutable application write paths and a machine-readable verifier.

This is not database immutability. A sufficiently privileged attacker who can both rewrite the database and obtain the integrity key can reconstruct valid hashes. Tail truncation combined with rollback of the mutable local chain head also requires an externally protected checkpoint to detect reliably. Production acceptance therefore still requires database least privilege, protected backup/recovery and—where the target control baseline requires it—approved immutable/WORM or external checkpoint evidence.

## RAG / prompt-injection boundary

Retrieved chunks remain permission-filtered and are serialized as explicitly untrusted evidence. Application instructions state that commands, role changes, tool requests, disclosure requests and policy overrides found inside evidence are data, not executable instructions. The system prompt also forbids disclosure of hidden system/developer instructions, security canaries, credentials, secrets or data outside authorized evidence.

Prompt framing is defense-in-depth, not proof of immunity. The repository includes deterministic tests of the boundary, and Issue #34 adds `evaluate_ai_security` for the actual configured provider. A real-model report is not accepted until a human reviewer assesses the complete responses; automatic canary checks alone are insufficient.

## Independent penetration test

Current state: **NOT SCHEDULED / NOT COMPLETED**.

Use `docs/PRE_V1_PENTEST_SCOPE.md` as the minimum scope and rules-of-engagement baseline. The independent assessor may expand it. At minimum the test must cover tenant isolation/IDOR, privilege escalation, authentication/MFA/session/CSRF, upload/download boundaries, connector SSRF, report rendering, AI/RAG leakage/prompt injection, audit/export behavior, and deployment configuration relevant to those controls.

## Security sign-off

Current state: **PENDING / BLOCKED FOR PRODUCTION APPROVAL**.

Use `docs/SECURITY_SIGNOFF.md` as the acceptance record. Sign-off requires:

1. exact-RC CI and release-security gates are green;
2. no unresolved Critical/High engineering or independent pentest finding remains;
3. all remaining findings have an owner, due date, disposition and retest evidence;
4. the independent penetration test is completed or formally scheduled according to the release policy;
5. the authorized real malware scanner is validated in the target environment;
6. the actual pilot AI model/version has a reviewed adversarial-evaluation report if AI is enabled;
7. audit-integrity and required immutable/WORM/external-checkpoint controls are validated in deployment;
8. real pilot production settings, backup/restore and operational boundaries are validated;
9. the named security and release approvers sign the record.

Until those items exist as evidence, Issue #8 must remain open.

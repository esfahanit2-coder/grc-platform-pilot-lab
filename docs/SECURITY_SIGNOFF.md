# Pre-v1 Security Sign-off Record

Status: **PENDING / BLOCKED FOR PRODUCTION APPROVAL**  
Parent issue: #8  
Repository preparation: #34  
Target: v1.0.0-rc1

This is the release-security acceptance record. It is intentionally incomplete until external and deployment evidence exists. Repository CI success alone is not security sign-off.

## 1. Release candidate identity

Complete for the exact candidate being approved:

- Release/tag: **PENDING**
- Git commit SHA: **PENDING**
- Backend image digest: **PENDING**
- Frontend image digest: **PENDING**
- Deployment/environment: **PENDING**
- Change freeze / candidate date: **PENDING**

Any code/configuration change after sign-off requires an explicit impact review and, where relevant, retest.

## 2. Evidence matrix

| Evidence | Required | Current state | Evidence reference |
| --- | --- | --- | --- |
| Exact-RC CI | Yes | PENDING for final RC | GitHub Actions run |
| Exact-RC Release Gate (SAST/secrets/container scans/SBOM) | Yes | PENDING for final RC | GitHub Actions run/artifacts |
| Migration/release rehearsal where applicable | Yes | PENDING for final RC PR | GitHub Actions artifact |
| Independent penetration test completed or formally scheduled | Yes | OPEN | Issue #8 / assessor evidence |
| Critical/High findings resolved | Yes | NOT YET ASSESSABLE | Independent finding tracker |
| Independent retest for remediated Critical/High findings | Yes | NOT YET ASSESSABLE | Retest report |
| Authorized real malware-scanner validation | Yes when Evidence upload enabled | OPEN | Pilot validation evidence |
| Actual pilot AI model adversarial evaluation | Yes when AI enabled | OPEN | `evaluate_ai_security` JSON + human review |
| Audit HMAC chain/verifier validation | Yes | Repository control complete; deployment evidence pending | `docs/AUDIT_INTEGRITY.md` + verifier report |
| Immutable/WORM or external audit checkpoint | Required when target baseline/contract requires it | OPEN / environment-specific | Architecture/control evidence |
| Production-equivalent TLS/cookie/CSRF settings | Yes | OPEN on target environment | Pilot deployment evidence |
| Backup/restore and operational recovery proof | Yes | OPEN on real pilot | Issue #7 / recovery evidence |
| Live connector validation | Required for enabled connectors | OPEN where applicable | Issue #6 |
| Content rights/provenance for loaded control packs | Required for production content | OPEN where applicable | Issue #5 |

## 3. Engineering security baseline already present

The repository currently contains automated coverage and/or release gates for the following controls. These are supporting evidence, not a substitute for the external evidence above:

- tenant isolation and cross-tenant IDOR negative paths;
- organization-scoped RBAC checks;
- auth/MFA/refresh throttling and TOTP replay resistance;
- cookie/CSRF negative paths;
- Evidence quarantine and fail-closed download boundary;
- connector SSRF/TLS/secret-handling controls;
- RAG scope/classification/untrusted-evidence framing;
- report renderer network/local-file blocking;
- sensitive export auditing;
- Audit Integrity HMAC chaining/verifier/historical sealing;
- SAST, secret scanning, container vulnerability gates and SBOM generation.

The latest known merged baseline before Issue #34 is commit `fcf370b38f8100320afd738cfa6fe4ca60c39650`, with post-merge CI #134 successful. Final sign-off must reference the later exact RC SHA rather than relying on this historical baseline.

## 4. Open release-security blockers

As of 2026-09-16:

1. independent penetration test is not completed or formally scheduled;
2. the authorized malware scanner has not been validated in a real target deployment;
3. the actual pilot AI model/version has not produced a human-reviewed adversarial evaluation report;
4. deployment-level audit immutable/WORM/external-checkpoint requirements are not yet evidenced;
5. real pilot production settings and operational validation remain incomplete;
6. final Critical/High finding status cannot be determined until the independent test is performed.

Therefore the current security decision is **BLOCKED / NOT APPROVED FOR PRODUCTION**.

## 5. Finding acceptance requirements

Before changing the decision to approved:

- every finding has an owner and due date;
- assessor severity is preserved;
- no Critical/High finding remains unresolved unless a formally approved risk exception explicitly allows release;
- remediated Critical/High findings have independent retest evidence;
- accepted residual risks identify approver, rationale, expiry/review date and compensating controls;
- all evidence references resolve to retained artifacts rather than informal chat or undocumented verbal approval.

## 6. AI security review record

Complete only if AI is enabled for the release:

- Tenant/provider evaluated: **PENDING**
- Provider type/model/version: **PENDING**
- Evaluation suite version: **PENDING**
- JSON evidence path/hash: **PENDING**
- Automatic canary checks: **PENDING**
- Human reviewer: **PENDING**
- Human review date: **PENDING**
- Prompt-injection/data-leakage findings: **PENDING**
- Retest evidence if remediated: **PENDING**

A mock-provider run is not valid production evidence.

## 7. Malware-scanner review record

Complete when Evidence upload/download is in production scope:

- Scanner product/version: **PENDING**
- Signature/database version/date: **PENDING**
- Network/deployment boundary: **PENDING**
- Known-clean result: **PENDING**
- Safe malware-test artifact result where policy permits: **PENDING**
- Timeout/unavailable behavior: **PENDING**
- Quarantine/download denial evidence: **PENDING**
- Reviewer/date: **PENDING**

## 8. Audit-integrity deployment review

- `verify_audit_integrity` valid-chain report: **PENDING on final environment**
- Disposable tamper/gap/head-mismatch validation: **PENDING on final environment**
- Dedicated production integrity-key custody reviewed: **PENDING**
- Backup/restore key continuity reviewed: **PENDING**
- Immutable/WORM/external checkpoint requirement decision: **PENDING**
- External checkpoint/WORM evidence if required: **PENDING**

## 9. Final decision

Select exactly one when all required evidence has been reviewed:

- [ ] **APPROVED** — all mandatory security acceptance criteria are satisfied.
- [ ] **APPROVED WITH CONDITIONS** — documented residual risks/conditions are explicitly accepted by authorized approvers and do not violate the release policy.
- [x] **BLOCKED / NOT APPROVED** — mandatory evidence or remediation remains incomplete.

Current rationale: external pentest/scheduling, real scanner validation, real-model adversarial evaluation, deployment audit-control evidence and final pilot validation are still missing.

## 10. Approvals

Do not pre-fill names or dates.

| Role | Name | Decision | Date | Evidence/signature reference |
| --- | --- | --- | --- | --- |
| Security owner | PENDING | PENDING | PENDING | PENDING |
| Release owner | PENDING | PENDING | PENDING | PENDING |
| Operations owner | PENDING | PENDING | PENDING | PENDING |
| Product/business risk owner (if residual risk accepted) | PENDING | PENDING | PENDING | PENDING |

When approval is issued, link the final signed/approved record from Issue #8 and preserve the exact release SHA and evidence artifacts used for the decision.

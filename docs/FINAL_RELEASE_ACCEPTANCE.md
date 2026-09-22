# Final datacenter release acceptance and customer UAT

Issue: #74  
Parent program: #68  
Repository baseline for this acceptance-control batch: `main@cf835537e3662bc320b4b20bc44b1b089831d864`

## Purpose

This runbook closes the gap between a green repository and a releasable customer datacenter candidate.

It does **not** convert repository CI into production acceptance. Final promotion remains blocked until the exact candidate release has real clean-host, content, connector, visual, security, operational and customer-UAT evidence as applicable.

The repository-side final gate is deliberately fail-closed:

- missing evidence is BLOCKED;
- failed evidence is FAIL;
- a later code/configuration change invalidates exact-release evidence until impact/retest is reviewed;
- no tag should be promoted because a checklist file merely exists.

## 1. Candidate identity and freeze

Select an exact candidate Git SHA only after:

1. required product/deployment work is merged;
2. exact-head PR CI and Release Gate pass;
3. post-merge push CI passes on `main`;
4. no known unreviewed release-impacting change is pending.

Record the same 40-character SHA in:

- the clean-host Pilot evidence generated for Issue #7;
- `runtime/final-release-attestations.json`;
- the security sign-off record;
- customer/UAT evidence and release/change records.

Do not reuse evidence from an older SHA unless a named reviewer explicitly performs and records an impact assessment that the release policy permits.

## 2. Reuse the existing real-evidence runbooks

Do not create parallel proof processes.

### Clean host / recovery — Issue #7

Use:

- `docs/PILOT_OPERATIONS.md`;
- `docs/PILOT_ACCEPTANCE_EVIDENCE.md`;
- `scripts/pilot-acceptance-evidence.py`.

Issue #7 must produce a real low-risk `acceptance-summary.json` with:

`ready_to_close_issue_7=true`

and its recorded release commit must exactly match the final candidate SHA.

This must come from the real clean/replacement host. CI, a mock deployment, or generated observation values are not valid substitutes.

### Authorized content — Issue #5

Use the existing customer-provided/content-pack mechanism and `docs/CONTENT_LICENSING.md`.

Final PASS requires the Issue #5 acceptance evidence actually to exist, including the authorized ISMS/ISO source/right-to-use record and required human-reviewed AFTA / ISMS / internal-baseline Common Control mapping.

Do not commit restricted standards text merely to satisfy UAT.

### Live connectors — Issue #6

Use `docs/CONNECTOR_PILOT_VALIDATION.md`.

Final PASS requires authorized live health/sync execution and the Issue #6 acceptance evidence. Synthetic provider fixtures remain regression evidence only.

At least three connector types must create real reusable Evidence objects when that remains the agreed Issue #6 acceptance scope.

### Security — Issue #8

Use:

- `docs/PRE_V1_SECURITY_VALIDATION.md`;
- `docs/SECURITY_SIGNOFF.md`;
- applicable restricted pentest/retest, scanner, AI and audit-control evidence.

The final gate must remain FAIL/BLOCKED while `docs/SECURITY_SIGNOFF.md` is BLOCKED / NOT APPROVED or while mandatory evidence is incomplete.

Repository SAST, dependency, secret and container scans are supporting evidence; they are not independent security sign-off.

### Visual Pilot — Issue #42

Capture genuine screenshots from the running candidate deployment.

Do not use generated/mock screenshots. Review them against the approved Persian dashboard direction and retain only screenshots that do not expose credentials, MFA data, sensitive customer Evidence or other restricted information.

## 3. One consolidated Pilot acceptance session

Where infrastructure and approvals permit, perform these in the same controlled candidate environment:

1. exact signed release install from the operator runbook;
2. production TLS/cookie/CSRF verification;
3. first tenant/admin bootstrap and MFA;
4. representative authorized content import;
5. representative customer/UAT dataset import;
6. primary GRC workflow UAT;
7. SMTP delivery acceptance if email is in deployment scope;
8. live connector acceptance when authorized endpoints are available;
9. Evidence real-scanner acceptance when Evidence upload is in production scope;
10. local-AI/no-AI/provider-switch and adversarial testing when AI is enabled;
11. dashboard screenshot capture for #42;
12. destructive backup/restore with measured RPO/RTO for #7;
13. monitoring/worker/queue/backup/support-bundle review;
14. security evidence review/sign-off;
15. customer/operator support handover.

This consolidation reduces repeated environment preparation. It does not weaken the independent approval boundary for #5, #6, #7, #8 or #42.

## 4. UAT journeys

Every journey must be executed against the exact candidate using real application/operator paths. Normal UAT must not depend on Django shell, direct database edits or hidden developer-only shortcuts.

Record PASS or FAIL, reviewer, timestamp and retained evidence reference for:

1. tenant onboarding, organization setup, authentication and MFA;
2. authorized framework/content import and version locking;
3. Asset/Process -> Risk -> Evaluation -> Treatment -> Action;
4. Common Control / Control Implementation -> reusable Evidence -> Test -> Assessment;
5. Finding -> CAPA/Action -> review/close;
6. internal audit and control testing;
7. controlled document create/version/submit/review/approve/history;
8. workflow assignment and permission-aware transition execution;
9. formal report preview/export;
10. Work Center / authoritative task execution;
11. user/role/scope administration plus audit trail and negative-scope checks;
12. customer import/export;
13. backup/restore/upgrade/support operator journey;
14. SMTP assignment/approval/retry/revoked-recipient handling when in scope;
15. live executive dashboard including intentional empty states where applicable.

Use `docs/FINAL_RELEASE_ATTESTATIONS.example.json` as the template. Keep the populated copy under ignored runtime/restricted evidence storage; do not commit customer sign-off details or sensitive evidence into Git.

## 5. UAT defect triage and retest

Every UAT defect must have:

- stable identifier;
- candidate SHA/environment;
- severity/impact;
- owner;
- disposition;
- remediation reference when code/config changes;
- retest evidence on the resulting candidate;
- explicit residual-risk acceptance when applicable.

A defect that requires a release-impacting code/configuration change creates a new candidate SHA. Re-run affected acceptance and all required exact-head/release gates. Do not silently carry PASS observations from the old candidate across the change.

No unresolved Critical/High release blocker may remain unless the governing release/security policy explicitly permits a documented, authorized exception.

## 6. Operator/support handover

Before customer acceptance, confirm ownership for:

- install/upgrade/rollback;
- backup/restore and retention;
- PKI/TLS renewal;
- secrets/credential rotation;
- monitoring/alert response;
- SMTP;
- scanner/signature updates;
- connector credentials/endpoints;
- local AI/model lifecycle if enabled;
- audit export/checkpoint handling;
- support-bundle collection and transfer;
- incident/escalation contacts and change management.

The handover must reference retained records rather than embedding secrets in the attestation JSON.

## 7. Build the final acceptance decision

Copy the template into ignored runtime storage:

~~~bash
cp docs/FINAL_RELEASE_ATTESTATIONS.example.json runtime/final-release-attestations.json
chmod 600 runtime/final-release-attestations.json
~~~

Populate entries only after the underlying observation/review has actually occurred.

Then run from the exact candidate checkout:

~~~bash
python3 scripts/final-release-acceptance.py \
  --pilot-summary artifacts/pilot-acceptance-<timestamp>/acceptance-summary.json \
  --attestations runtime/final-release-attestations.json \
  --release-sha <EXACT_CANDIDATE_SHA> \
  --out artifacts/final-release-acceptance.json \
  --require-complete
~~~

The resulting schema is:

`grc-final-release-acceptance-v1`

The aggregator verifies:

- Issue #7 real-pilot summary is complete;
- Issue #7 evidence references the exact candidate SHA;
- the attestation file declares the same release SHA;
- all mandatory external gates are PASS;
- every required UAT journey is PASS;
- the local tracked repository checkout is clean and on the candidate SHA;
- human evidence entries have bounded, secret-safe metadata and evidence references.

It does not fetch or copy secret-bearing evidence into the output.

## 8. Promotion rule

A release candidate may proceed to the promotion decision only when:

`promotion_ready=true`

in the final acceptance JSON **and** the named release/security/customer owners have reviewed the referenced underlying evidence according to policy.

`promotion_ready=true` is an aggregation result, not a cryptographic signature and not an autonomous release authorization.

Do **not** create/promote `v1.0.0-rc1` or `v1.0.0` merely because:

- repository CI is green;
- #73 deployment tooling is complete;
- the acceptance aggregator executes;
- a template was filled with unsupported PASS values.

If any underlying evidence changes, expires, belongs to another SHA/environment or is later found invalid, the release decision must return to BLOCKED pending review/retest.

## 9. Current blocker state

At the start of this #74 repository-control batch:

- #73 production datacenter packaging: completed and post-merge CI green on `main@cf835537e3662bc320b4b20bc44b1b089831d864`;
- #5: OPEN — authorized ISMS source/right-to-use + reviewed three-way mapping still required;
- #6: OPEN — authorized live connector evidence still required;
- #7: OPEN — real clean-host/TLS/destructive recovery/RPO-RTO/local-AI evidence still required;
- #8: OPEN — independent/deployment security acceptance and named sign-off still required;
- #42: OPEN — genuine running-Pilot visual evidence still required;
- #74: OPEN — final real customer/operator UAT and promotion decision not yet complete.

This repository batch must not close those issues automatically.

## 10. GitHub evidence boundary

Safe GitHub evidence may include concise, reviewed summaries, exact release SHA, CI/run references and non-sensitive acceptance statuses.

Do not attach:

- environment/secret files;
- TLS private keys;
- connector/SMTP/scanner credentials;
- database dumps or object-store backups;
- raw customer Evidence/data;
- restricted licensed standards text;
- full AI prompts/responses/canaries;
- raw sensitive application/security logs;
- restricted pentest artifacts when policy prohibits publication.

Issue #74 closes only after the actual external blockers applicable to the customer are resolved or formally/contractually excluded by authorized owners, representative UAT is passed/retested, security and operations sign-off are complete, and the final candidate promotion decision is approved.

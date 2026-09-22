# Clean-host Pilot Acceptance Evidence

Status: **execution runbook — real host evidence still required**  
Parent: Issue #7  
Security acceptance overlap: Issue #8

This runbook turns the existing pilot operations procedures into a repeatable evidence package. It does **not** replace the actual clean-host deployment, destructive backup/restore drill, network controls, independent penetration test, or human security review.

The collector is deliberately fail-closed: missing evidence becomes `NOT_MEASURED` or `MANUAL_REQUIRED`, never `PASS`.

## Evidence boundary

The low-risk acceptance bundle may contain:

- exact Git release commit;
- tracked checkout cleanliness;
- allowlisted OS/runtime metadata;
- Docker/Compose version and service-state output;
- `pilot_readiness` results;
- TLS certificate/trust metadata and HTTP status;
- sanitized backup/restore observation metadata;
- sanitized adversarial-AI result metadata;
- explicit operator attestations and evidence references;
- final PASS/FAIL/NOT_MEASURED/MANUAL_REQUIRED summary.

The bundle must **not** contain:

- `.env` contents or environment dumps;
- TLS private keys or certificate PEM bodies;
- PostgreSQL dumps, object-store archives, restored customer payloads, or secret-bearing `config.env` backup files;
- application/service logs;
- connector credentials, tokens, API keys, authorization headers, or URLs containing credentials;
- AI prompts, model responses, synthetic canary values, or the full adversarial-AI report.

`runtime/`, `backups/`, and `artifacts/` are ignored by Git. Do not override those ignores to commit operational evidence.

## 1. Start from the approved release

On the clean/replacement pilot host, check out the exact approved release commit and confirm that no tracked local modification exists before the drill.

Record the deployment/change ticket or other internal provenance in the `clean_host_confirmed` operator attestation. The collector can record the commit and checkout state, but it cannot prove by itself that the machine was clean before deployment.

## 2. Deploy and validate the runtime

Follow `docs/PILOT_OPERATIONS.md` for `.env`, TLS, Compose, migrations and initial readiness.

For a TLS deployment, use the approved hostname and CA-trusted certificate. The collector performs certificate chain/hostname verification; browser-authenticated cookie and CSRF behavior remains a manual acceptance observation.

## 3. Perform the destructive backup/restore drill

Use the existing runbook and scripts. The drill must include controlled markers so data-loss boundaries are observable rather than inferred.

Recommended sequence:

1. Create a uniquely identifiable application marker and at least one Evidence object **before** backup.
2. Record the Evidence object application checksum in the restricted drill record.
3. Run `scripts/pilot-backup.sh` with the approved backup name.
4. Confirm `backup-observation.json` exists under the resulting ignored `backups/<name>/` directory.
5. Create a second uniquely identifiable marker **after** backup.
6. Restore the selected backup using `scripts/pilot-restore.sh` on the approved clean/replacement host or approved destructive-test environment.
7. Confirm `restore-observation.json` exists.
8. Verify the pre-backup marker exists after restore.
9. Verify the post-backup marker does **not** exist after restore.
10. Download the restored Evidence object through the application path and verify its application checksum.
11. Review the measured recoverable cutoff and `observed_rto_seconds` against the approved RPO/RTO objectives.

The collector copies only sanitized observation metadata. It never copies the database dump, object archive, TLS key, or secret-bearing backup configuration.

## 4. Prove local AI under the intended network boundary

Block internet egress according to the approved pilot network design before running the local-model acceptance test. Keep only the connectivity required for the approved on-prem services.

Run core + local-AI readiness through the collector by providing the real `AIProviderConfig` ID. This exercises the existing `pilot_readiness --ai-provider-id ...` generation and embedding checks.

The network control itself must be recorded as `internet_egress_blocked_during_ai` with a firewall/change/evidence reference. A successful local generation call alone does not prove that Internet egress was blocked.

Also exercise AI-disabled mode and approved provider switching and record the result as `ai_disable_provider_switch`.

## 5. Optional Issue #8 adversarial AI evidence

The collector can invoke the existing real-model evaluator when `--ai-tenant-code` is provided. It holds the full evaluator JSON only in process memory and writes only a sanitized summary to the low-risk bundle.

For formal Issue #8 review, keep any full adversarial report that contains model responses and synthetic canaries in a **restricted operational evidence location**, not in GitHub and not in the low-risk bundle. A named security reviewer must inspect the full responses and record the decision under `ai_human_review` with an internal evidence reference.

Automatic canary checks are necessary evidence, not final model-security acceptance.

## 6. Fill the operator attestation file

Copy the committed template into ignored runtime storage:

```bash
cp docs/PILOT_MANUAL_OBSERVATIONS.example.json runtime/pilot-manual-observations.json
chmod 600 runtime/pilot-manual-observations.json
```

Replace every placeholder only after the observation has actually been performed. Allowed statuses are `PASS` and `FAIL`. An incomplete or malformed entry becomes `MANUAL_REQUIRED`.

At minimum, Issue #7 needs real observations for:

- clean-host provenance;
- HTTPS authenticated secure-cookie/CSRF behavior;
- restore marker proof;
- restored Evidence checksum proof;
- blocked Internet egress during local AI;
- AI-disable/provider-switch behavior;
- monitoring/logging/background-processing health;
- RPO acceptance;
- RTO acceptance.

The template also tracks Issue #8 external observations so the same drill can reference scanner, immutable-audit-storage, AI human review and pentest evidence without falsely closing #8.

## 7. Generate the low-risk bundle

Example TLS + local-AI run:

```bash
python3 scripts/pilot-acceptance-evidence.py \
  --tls \
  --base-url https://grc-pilot.example.internal/ \
  --ai-provider-id <REAL_AI_PROVIDER_UUID> \
  --ai-tenant-code <PILOT_TENANT_CODE> \
  --backup-observation backups/<BACKUP_NAME>/backup-observation.json \
  --restore-observation backups/<BACKUP_NAME>/restore-observation.json \
  --manual-observations runtime/pilot-manual-observations.json \
  --require-complete
```

If `--require-complete` is omitted, the collector can be run early to show what is still missing. This partial mode is intentionally useful during the drill and cannot convert missing evidence to `PASS`.

Default output is an ignored directory such as:

```text
artifacts/pilot-acceptance-20260916T200000Z/
```

The key files are:

- `acceptance-summary.json` — machine-readable acceptance state;
- `acceptance-summary.txt` — concise human view;
- `release-commit.txt`;
- `host-os.json`;
- low-risk Docker/Compose/readiness observations when available;
- `tls-endpoint.json` when a base URL is supplied;
- sanitized backup/restore summaries;
- `ai-security-summary.json` when adversarial evaluation is requested;
- sanitized operator-attestation summary.

## 8. Issue #7 closure rule

Do **not** close Issue #7 merely because the collector executes successfully.

Closure requires:

1. `acceptance-summary.json` has `ready_to_close_issue_7=true`;
2. a human reviewer confirms the referenced external/manual evidence actually exists and belongs to the tested release/environment;
3. the exact release commit in the bundle matches the release under acceptance;
4. no Issue #7 required check was waived by silently omitting a test;
5. RPO/RTO were measured from the destructive drill, not inferred from configuration or CI.

If any required evidence is absent, malformed or failed, Issue #7 stays open.

## 9. Issue #8 remains independent

A successful Issue #7 clean-host drill does not by itself close Issue #8. Pre-v1 security acceptance still requires its applicable external evidence, including independent pentest/retest or approved schedule, real malware-scanner validation, real-model human review, deployment-level immutable/WORM or external audit-checkpoint evidence where required, and final named security sign-off.

The collector tracks some of these observations only to make cross-reference easier. It is not a substitute for the security acceptance process documented in `docs/PRE_V1_SECURITY_VALIDATION.md`, `docs/PRE_V1_PENTEST_SCOPE.md`, and `docs/SECURITY_SIGNOFF.md`.

## 10. What may be attached to GitHub

Preferred GitHub evidence for Issue #7 is the low-risk `acceptance-summary.json` plus concise reviewer commentary. Attach additional bundle files only after manual inspection for environment-sensitive information.

Never attach the backup directory, `.env`, TLS private key, full AI adversarial report, raw application logs, connector credentials, customer evidence payloads, or any other secret-bearing operational artifact.

# Pre-RC Performance and Load Validation

## Purpose

This runbook defines repeatable engineering performance checks for the GRC Platform before `v1.0.0-rc1`.

It deliberately separates three different kinds of evidence:

1. **Query-amplification regression tests in CI** — prove selected list APIs do not add SQL queries linearly per returned row.
2. **Deterministic harness self-test in the release gate** — proves the load tool itself can execute bounded concurrent HTTP requests and produce latency/error/throughput summaries.
3. **Representative pilot-host load measurements** — the only source that may be used for real capacity/sizing conclusions.

GitHub-hosted runner latency or throughput is **not** production capacity evidence and must not be presented as an SLO.

## What is covered

The current pre-RC baseline covers:

- authentication token requests;
- management dashboard reads;
- risk list and optional risk detail;
- control list and optional control detail;
- assessment list and optional assessment detail;
- one explicitly opt-in write scenario for a disposable pilot tenant;
- p50, p95, mean and maximum latency;
- attempted requests/second throughput;
- error rate, HTTP status distribution and bounded error summaries;
- machine-readable JSON output;
- query-count regression tests for risks, controls, assessments and assessment items.

## Safety rules

- Prefer a dedicated non-production pilot tenant.
- Use a dedicated low-privilege load-test user; do not hammer a human administrator account.
- Pass credentials/tokens through environment variables, not command history or committed files.
- Default harness scenarios are read-only.
- Write load requires the explicit `--allow-writes` flag plus an endpoint and JSON payload file.
- Never point destructive/write scenarios at production data.
- Start at low concurrency and increase only after monitoring DB, application, worker and host resources.
- Do not disable tenant/RBAC/security controls to make a benchmark look better.

## CI / release-gate checks

The Django suite includes `apps.common.test_performance_regressions.QueryAmplificationRegressionTests`. Each selected endpoint is measured with a small result set, then with more rows; query count may only grow by a small fixed budget rather than per-row.

The release gate runs:

```bash
python scripts/http-load-smoke.py --self-test
```

The self-test starts a loopback-only local HTTP server, exercises bounded concurrent GET/POST requests and validates percentile, error and throughput calculations. It does not call the GRC runtime and therefore adds only a very small deterministic gate cost.

## Environment variables

Recommended variables for a protected pilot run:

```bash
export GRC_BASE_URL='https://grc-pilot.example.internal'
export GRC_TENANT_ID='<tenant-uuid>'
export GRC_ACCESS_TOKEN='<short-lived-access-token>'
export GRC_LOAD_LABEL='pilot-host-a-2026-09-16'
```

For the optional authentication scenario:

```bash
export GRC_AUTH_USERNAME='<dedicated-load-user>'
export GRC_AUTH_PASSWORD='<secret>'
```

Optional existing object IDs enable detail-path scenarios:

```bash
export GRC_LOAD_RISK_ID='<risk-uuid>'
export GRC_LOAD_CONTROL_ID='<control-uuid>'
export GRC_LOAD_ASSESSMENT_ID='<assessment-uuid>'
```

Do not commit these values.

## Read-only pilot profile

Initial recommended measurement profile:

```bash
python scripts/http-load-smoke.py \
  --requests 100 \
  --concurrency 8 \
  --warmup 5 \
  --timeout 15 \
  --max-p95-ms 750 \
  --max-error-rate 0.01 \
  --min-throughput-rps 10 \
  --output performance-read.json
```

Default read scenarios are:

- `/api/v1/dashboard/management/`
- `/api/v1/risks/?page=1`
- `/api/v1/controls/?page=1`
- `/api/v1/assessments/?page=1`

If the three `GRC_LOAD_*_ID` variables are set, risk/control/assessment detail scenarios are added automatically.

## Authentication-only profile

Authentication should be measured separately so its latency/throughput budget is not hidden inside read-path totals:

```bash
python scripts/http-load-smoke.py \
  --auth-only \
  --requests 40 \
  --concurrency 4 \
  --warmup 3 \
  --max-p95-ms 1000 \
  --max-error-rate 0.01 \
  --min-throughput-rps 4 \
  --output performance-auth.json
```

A successful password login may return a token directly or an MFA challenge (`202`) depending on the test account. Use a dedicated account whose expected MFA state is known. A policy response requiring setup/error should be treated as a failed benchmark setup rather than silently ignored.

## Optional write profile

Writes are disabled unless explicitly opted in. Use a disposable tenant and a payload that can safely create/update isolated test data.

```bash
python scripts/http-load-smoke.py \
  --requests 30 \
  --concurrency 2 \
  --warmup 2 \
  --allow-writes \
  --write-method POST \
  --write-endpoint '/api/v1/<safe-test-resource>/' \
  --write-payload-file ./runtime/perf-write.json \
  --max-p95-ms 1500 \
  --max-error-rate 0.01 \
  --min-throughput-rps 2 \
  --output performance-write.json
```

The payload file must not contain secrets and should stay outside committed repository content.

## Provisional engineering budgets

These values are **starting pre-RC engineering budgets for the intended pilot hardware class**, not contractual SLOs and not claims that the current system has already achieved them:

| Profile | p95 latency | Error rate | Attempted throughput |
|---|---:|---:|---:|
| Read-only dashboard/list/detail | `<= 750 ms` | `<= 1%` | `>= 10 req/s` at concurrency 8 |
| Authentication-only | `<= 1000 ms` | `<= 1%` | `>= 4 req/s` at concurrency 4 |
| Controlled disposable-tenant write | `<= 1500 ms` | `<= 1%` | `>= 2 req/s` at concurrency 2 |

These budgets must be confirmed or revised after the first representative clean-host pilot measurement. Any revision should record host sizing, database/object-store placement, dataset size, concurrency, commit/release version and the reason for changing the budget.

## Interpreting throughput

`throughput_rps` is calculated as attempted measured requests divided by the measured wall-clock window for the scenario. It is not CPU-normalized and cannot be compared fairly across materially different hardware/network environments without recording those differences.

For multi-scenario runs, overall throughput uses the sum of measured scenario windows because scenarios are executed sequentially. Use the per-scenario numbers for diagnosis and sizing discussions.

## Machine-readable evidence

The JSON report uses schema `grc-performance-v2` and records:

- target label and sanitized base URL;
- request count, concurrency, warmup and timeout;
- whether auth/detail/write scenarios were enabled;
- per-scenario and overall p50/p95/max/mean latency;
- attempted throughput RPS;
- error rate and status counts;
- bounded error categories;
- measured wall-clock request window.

Store representative pilot reports with the release/pilot evidence package, not as anonymous screenshots.

## Minimum evidence for pre-RC review

Before treating performance readiness as validated on a real pilot environment, record:

- exact Git commit/release;
- host CPU/RAM/storage and virtualization context;
- PostgreSQL/object-store/Redis placement;
- approximate tenant dataset sizes (risks, controls, requirements, assessments, evidence metadata);
- command/profile used;
- JSON output artifacts;
- resource observations during the run;
- any endpoint exceeding budget and the remediation/retest result.

The software/tooling portion of #20 can be completed in CI, but capacity claims remain environment-specific and must be re-measured on representative pilot hardware.

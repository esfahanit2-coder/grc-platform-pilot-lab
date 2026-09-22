# Connector pilot validation runbook

This runbook covers Issue #6 for the first read-only evidence-collection pilot.

## Validation stages

Connector readiness is tracked in two explicit stages:

1. **Offline provider-contract validation** — synthetic fixtures exercise parsing, normalization, evidence metadata, audit boundaries, secret handling and the human-review boundary without requiring access to customer infrastructure.
2. **Live validation** — the same connector code is run against authorized representative infrastructure and must pass health/sync checks before the connector is considered live-validated.

Passing the offline stage is not a claim that a vendor/version combination has been proven against a real appliance or server.

## Scope

Supported connector types:

- Active Directory / LDAP
- FortiGate REST API
- Veeam Enterprise Manager
- Tenable / Nessus API

The repository contains connector implementations, normalized provider contracts and synthetic contract fixtures. A connector is **not** considered live-validated until its health and sync operations succeed against an authorized representative system.

## Security boundaries

- Credentials are referenced only by environment-variable names. Literal secrets must not be stored in `ConnectorConfig`.
- Production HTTP connectors require HTTPS and TLS verification.
- Redirects are disabled.
- HTTP request paths cannot override the configured host.
- FortiGate collection is restricted to configured `/api/v2/` read paths, maximum 10 per run.
- On-premises private RFC1918/ULA addresses are allowed by design.
- Loopback, link-local/cloud-metadata, multicast, unspecified and reserved address classes are rejected.
- Connector response size and request timeout remain bounded by application settings.
- Failed-run messages are redacted against configured credential environment-variable values before persistence/audit.
- Collected connector facts become Evidence only. They do not mark a control effective or a requirement compliant.
- DNS/IP allowlisting at deployment remains recommended for management endpoints, particularly where internal DNS can change dynamically.

## Normalized provider contract

Provider responses are reduced to bounded, reviewable facts rather than being treated as compliance decisions. Each normalized payload carries:

- `schema_version`;
- `provider`;
- `dataset`;
- a bounded `summary`;
- provider-specific facts/samples required for human review.

The current datasets are:

- FortiGate: `security_configuration`;
- Tenable / Nessus: `scan_inventory`;
- Veeam: `backup_assurance`;
- Active Directory: `account_hygiene`.

Synthetic fixture data lives at `backend/apps/connectors/fixtures/provider_contracts.json`. It contains no production endpoint, credential or customer data and exists only to verify deterministic parsing/normalization behavior.

## Evidence contract

A successful sync creates one reusable `Evidence` object with:

- tenant and organization-unit scope;
- connector type and connector id;
- connector run id;
- collection timestamp;
- source hostname;
- SHA-256 of the normalized collected payload;
- normalized provider schema version, provider, dataset and fact summary;
- `collection_mode=read_only`;
- `human_review_required=true`;
- `asserts_compliance=false`.

The evidence can later be linked to an assessment item, control implementation/test, workpaper or other supported object through the normal Evidence linking workflow. That linkage does not change the target object's compliance/effectiveness state automatically. Regression tests explicitly enforce this boundary.

## Provider collection profiles

### Active Directory / LDAP

Configuration:

- `configuration.host` or `base_url`;
- `configuration.base_dn`;
- `configuration.use_ssl` (prefer true);
- optional `configuration.port`, `search_filter`, `attributes`, `size_limit` (1..10000);
- optional `configuration.privileged_groups` with up to 50 group names or DNs;
- optional `configuration.include_sample` (default false);
- username environment-variable name;
- password environment-variable name.

Default collection derives account-hygiene facts from `userAccountControl` and membership metadata, including disabled accounts, `PASSWORD_NOT_REQUIRED`, `PASSWORD_NEVER_EXPIRES`, and matches against configured privileged groups. Account samples are opt-in rather than stored by default.

Use an account limited to directory read operations required by the configured search.

### FortiGate

Configuration:

- HTTPS `base_url`;
- API-token environment-variable name;
- `configuration.collection_profile`: `minimal` or `baseline` (default `baseline`);
- optional explicit `configuration.read_paths` under `/api/v2/`, which override the profile.

`minimal` reads `/api/v2/cmdb/system/global`.

`baseline` reads the system status, administrator metadata, firewall policy metadata and interface metadata and normalizes only bounded review fields. No write endpoint is used.

Use a least-privilege API administrator/profile that permits only the required read endpoints.

### Veeam Enterprise Manager

Configuration:

- HTTPS `base_url`;
- username environment-variable name;
- password environment-variable name.

The connector opens an Enterprise Manager API session and reads backups and backup sessions. The normalized contract exposes bounded backup/session inventory and result/state counts; it does not declare recoverability or control effectiveness by itself.

### Tenable / Nessus

Configuration:

- HTTPS `base_url`;
- access-key environment-variable name;
- secret-key environment-variable name.

The connector reads scan inventory from `/scans` and stores a bounded normalized summary of scan identity, status and modification time. Vulnerability/compliance conclusions remain part of later human-reviewed assessment workflows rather than being inferred from scan presence alone.

## Offline acceptance checklist

CI must prove that:

1. synthetic payloads for all four providers normalize to schema-versioned datasets;
2. connector-generated Evidence preserves provider/dataset/summary metadata and a deterministic payload hash;
3. failed runs remain diagnosable while configured credential values are redacted;
4. SSRF/path/credential configuration guards are enforced;
5. connector Evidence can be linked to a control implementation without changing its implementation/effectiveness state;
6. all existing Golden Pilot and connector regression tests still pass.

## Live acceptance checklist

For each available pilot system:

1. Create a tenant-scoped connector configuration without literal secrets.
2. Run `health`; confirm success is audited as `connector.health`.
3. Run `sync`; confirm one `ConnectorRun` finishes `succeeded`.
4. Confirm reusable Evidence is created with provenance metadata and payload hash.
5. Link the Evidence through the normal evidence workflow to a relevant control test or assessment item.
6. Verify the target control/assessment remains unchanged until a human performs the normal review/update action.
7. Trigger one controlled failure (for example a deliberately unavailable test endpoint or revoked test credential) and verify the failed run and redacted diagnostic are visible.
8. Record the tested product/version because vendor API response shapes may differ between releases.

## Issue #6 completion rule

Do not close Issue #6 from mocked or synthetic tests alone. Completion requires live health/sync evidence for each available pilot system and at least three connector types producing reusable Evidence objects against authorized representative infrastructure.

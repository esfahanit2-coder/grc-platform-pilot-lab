# GRC Platform — Connector Strategy

## Purpose

Connectors reduce manual evidence collection by reading facts from enterprise infrastructure and normalizing them into auditable GRC Evidence. They are not policy engines and do not autonomously determine compliance.

## Current pilot providers

- Active Directory / LDAP
- FortiGate REST API
- Veeam Enterprise Manager
- Tenable / Nessus

Future providers should follow the same contract rather than create one-off assurance logic.

## Core connector contract

Every connector should have:

1. **Configuration** — provider type, target, tenant/org scope, safe options and secret-reference names.
2. **Health check** — test reachability/authentication without mutating the target.
3. **Read-only sync** — collect bounded provider facts.
4. **Normalization** — convert provider-specific payloads into stable product datasets/schema versions.
5. **ConnectorRun** — persist status, timestamps, diagnostics and collection metadata.
6. **Evidence creation** — produce reusable Evidence with source, scope, time, provider, run ID and normalized payload integrity hash.
7. **Human review boundary** — mark automated collection as advisory; never assert compliance/effectiveness.

## Security requirements

- Literal secrets must not be stored in configuration or repository content.
- Secret fields reference approved environment/secret-store variable names.
- Production HTTP targets require TLS unless an explicitly approved deployment exception exists.
- Redirects should be disabled where they could bypass validated target boundaries.
- Host/path validation must prevent escaping the configured target.
- Loopback/link-local/multicast/unspecified/reserved destinations are blocked; private RFC1918/ULA addresses remain valid because on-prem systems are a primary use case.
- Response size/time limits must prevent unbounded collection.
- Persisted errors must be redacted and must never contain configured secret values.

## Evidence metadata expectations

Connector-produced Evidence should retain enough metadata to answer:
- which tenant/org scope did this collection belong to?
- which connector/provider/config created it?
- which run created it?
- which source host/system was queried?
- when was it collected?
- which normalized dataset/schema version was produced?
- what is the integrity hash of the normalized payload?
- was it automated/read-only?
- does it require human review?
- does it assert compliance? (must be false for current connector model)

## Provider-specific direction

### AD/LDAP
Focus on identity/account/security hygiene facts such as disabled accounts, privileged-group membership and relevant account flags. Use bounded searches and configurable base/scope. Do not perform identity administration.

### FortiGate
Use read-only REST paths. Collection profiles may include system status, administrators, policies/interfaces and other explicitly approved GET datasets. Bound the number of paths and keep them under the intended FortiGate API namespace.

### Veeam
Use read-oriented Enterprise Manager/API flows to collect backup assurance facts such as backup inventory/state relevant to the defined dataset. Do not start/stop backup jobs.

### Tenable/Nessus
Collect bounded scan/vulnerability inventory summaries and evidence. The connector should not become a scanner implementation; it integrates with scanner products and normalizes results.

## Operational UX

Connector Operations should expose:
- active/inactive state;
- provider and safe target metadata;
- TLS verification state;
- last sync/status;
- redacted last error;
- health action;
- read-only sync action;
- recent ConnectorRun history;
- dataset/schema summary;
- created Evidence identifiers/provenance.

Never show literal secret values.

## Live validation policy

Synthetic fixtures and mocked provider contracts are required for CI but do not prove real infrastructure interoperability. Issue #6 remains incomplete until authorized live internal systems are exercised and at least three connector types create real reusable Evidence.

## Future connector direction

Additional connectors may cover endpoint/security tooling, SIEM/logging, cloud/IAM, ticketing, CMDB/asset sources, backup platforms and other assurance systems. New connectors should reuse the same run/normalization/evidence/human-review contract rather than introduce provider-specific compliance logic.

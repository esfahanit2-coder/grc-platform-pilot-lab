# ADR-006: Frameworks are versioned content, not application code

## Decision

Frameworks, regulations, maturity models and customer questionnaires are represented by the generic `Framework -> FrameworkVersion -> Requirement` model. A version can be locked and becomes immutable. Cross-framework relationships are tenant-owned `RequirementMapping` records.

## Consequences

- New frameworks do not require backend releases.
- Historical assessments can later point to immutable framework versions.
- Copyright/licensing metadata stays attached to content.
- Global reference content is read-only to tenants; tenants may duplicate it before customization.

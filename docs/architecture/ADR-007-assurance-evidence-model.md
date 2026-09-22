# ADR-007 — Assurance, Compliance and Evidence Model

## Status
Accepted for Sprint 4.

## Context
A GRC platform must preserve historical assessments while allowing Framework content to evolve, reuse the same proof across multiple assurance contexts, and keep remediation connected to the originating non-conformity.

## Decisions

### 1. Requirement is not an assessment result
`Requirement` is reference content. `AssessmentItem` holds the result for a specific Assessment.

### 2. Assessments snapshot critical Requirement data
At Assessment creation, each assessable Requirement produces an AssessmentItem that snapshots code, title, body and weight. The referenced tenant FrameworkVersion is locked before assessment creation.

### 3. Compliance status is not stored on Requirement
Compliance is calculated from AssessmentItems. This permits the same Requirement to be compliant in one business unit and non-compliant in another, and preserves history across assessment periods.

### 4. Evidence is a first-class reusable object
Evidence is stored once and linked through `EvidenceLink` to assurance objects. It is tenant-owned, optionally organization-scoped, hashable and version-ready.

### 5. Evidence reuse must not bypass scope
Scoped Evidence may only be linked to a target in the same organization scope. Tenant-wide Evidence requires whole-tenant management permission.

### 6. Findings are explicit assurance objects
A Finding can originate from an AssessmentItem and carry Requirement, Control Implementation and Risk context. Findings do not embed corrective actions; generic `Action` objects reference the Finding.

### 7. Closure is verified, not a generic status edit
A Finding cannot be PATCHed directly to `closed`. The close workflow verifies corrective-action state and records closer, time and closure comment.

### 8. Compliance scoring is replaceable
Sprint 4 ships with default status factors but stores them as configurable assessment metadata. Future content packs can supply assessment-specific scoring models without changing application code.

## Consequences

- historical assessment reports remain stable after Framework evolution;
- Evidence duplication is reduced;
- the same assurance core can serve ISO, AFTA, COBIT, quality and maturity assessments;
- generic link targets require strict server-side tenant/scope validation;
- file malware scanning remains a separate security adapter and must be completed before high-assurance production use.

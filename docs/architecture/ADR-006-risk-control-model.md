# ADR-006 — Separate Control Definition, Implementation and Risk Evaluation History

## Decision

1. A `Control` is a reusable definition and may be global or tenant-owned.
2. A `ControlImplementation` is the tenant/org-unit-specific execution of that control.
3. Risk scores are not columns on `Risk`; every inherent/current/residual/target calculation is an immutable-ish historical `RiskEvaluation` record.
4. `RiskControl` connects a risk to an actual control implementation, not merely to a control definition.

## Why

The same control can be implemented differently across companies and business units. A risk also needs a historical trail of changing scores. Mixing these concepts would make holding-company reporting, audits and multi-framework reuse unreliable.

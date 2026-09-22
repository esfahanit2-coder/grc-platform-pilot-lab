# ADR-008 — Audit, Control Testing and Document Factory

## Decision
1. Internal audit is a separate domain from immutable application audit logs.
2. Control test definitions are separated from test runs so evidence/history is never overwritten.
3. Controlled documents use Document → Version → Approval; the current version is a pointer, not mutable content.
4. Formal outputs such as SoA and Audit Report are generated from domain data through a report boundary.
5. Evidence remains reusable and may link to audit workpapers and control test runs.

## Consequences
- Audit history remains stable.
- Automated control testing can be added later without changing the model.
- Custom DOCX templates can replace the minimal built-in generators in a later sprint.

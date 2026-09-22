# ADR-007: Content pack imports are dry-run first and atomic

Imports support JSON and XLSX in Sprint 2. The entire pack is validated before persistence, and commit occurs inside a database transaction. Source SHA-256 is retained for provenance. Future signed pack support can build on the same format without changing domain entities.

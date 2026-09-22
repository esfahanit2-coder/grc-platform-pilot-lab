# Sprint 2 — Framework Engine

Sprint 2 introduces the first GRC-domain core.

Implemented:

- Global/reference versus tenant-owned framework boundaries.
- Framework versions and immutable locking.
- Hierarchical requirements.
- Per-requirement translations.
- JSON/XLSX dry-run and atomic import.
- JSON/XLSX export.
- SHA-256 import provenance and canonical locked-version checksum.
- Tenant-owned crosswalk mappings with mapping type, strength, confidence, provenance and approval.
- Framework-specific RBAC permissions.
- Basic RTL Framework Library, Requirement Tree, Import and Crosswalk UI.

A framework is content. No backend code may branch on a framework code such as `if framework == ISO27001`.

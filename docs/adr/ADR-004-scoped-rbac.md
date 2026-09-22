# ADR-004 — Scoped RBAC

## Decision

Authorization uses Permission → Role → UserRoleScope. A role assignment may be tenant-wide (`organization_unit = null`) or restricted to one organization subtree.

## Consequences

- Tenant-level administration requires a whole-tenant assignment.
- Organization APIs filter querysets to assigned subtrees.
- Domain modules added later must reuse the same scope service rather than implementing custom authorization rules.

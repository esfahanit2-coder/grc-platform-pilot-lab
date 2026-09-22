# Sprint 0 Architecture Notes

## Request path for tenant-scoped APIs

```text
JWT authentication
      ↓
X-Tenant-ID parsed by middleware
      ↓
TenantMembership validated in API tenant context
      ↓
Queryset filtered by tenant_id
      ↓
Object-level scope/permission checks
      ↓
Domain service
```

`X-Tenant-ID` is a selector, not an authorization credential.

## Sprint 0 deliberate omissions

Framework Engine, Risk Engine, dashboards, reporting and AI are intentionally not implemented in this starter. Sprint 0 establishes the secure platform foundation first.

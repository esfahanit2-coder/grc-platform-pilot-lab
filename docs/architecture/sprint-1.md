# Sprint 1 — Identity, Scoped RBAC, MFA and Tenant Administration

Sprint 1 upgrades the Sprint 0 foundation into an operational identity and tenant-security layer.

## Delivered

- Permission catalog and tenant-specific roles.
- User role assignments with optional organization-unit scope.
- Scoped organization queries and hierarchy tree API.
- Whole-tenant permission enforcement for tenant administration, membership, role administration, security settings and audit trail.
- Tenant user administration without globally disabling a user who belongs to another tenant.
- TOTP MFA with encrypted secrets.
- MFA challenge flow for normal login.
- Mandatory first-login MFA enrollment when a tenant requires MFA.
- Tenant security settings: MFA requirement, password minimum length, session policy placeholder.
- Correlation IDs returned as `X-Request-ID`.
- Professional audit events with actor, outcome, request metadata and before/after values.
- Audit event query API.
- Tenant provisioning API for system administrators.
- Organization hierarchy cycle protection and cross-tenant manager/parent protection.
- Frontend pages for login/MFA, organization tree, tenant users, roles and tenant security.

## Security boundary

Organization-scoped roles can only operate inside their assigned subtree. Tenant-wide operations require a role assignment with no organization scope. This prevents a scoped administrator from escaping their subtree by creating a new root unit or changing tenant-level security settings.

## Deferred

- SAML/OIDC/LDAP/AD providers.
- FIDO2/WebAuthn.
- Token revocation/blacklist administration.
- SCIM provisioning.
- ABAC.
- Fine-grained audit-log scoping by organization object lineage.

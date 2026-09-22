# ADR-008 — Conditional enterprise SSO with OIDC preference

## Status

Accepted as an architecture and scope decision.

No enterprise-SSO implementation is authorized by this ADR alone. Implementation begins only when a target customer's identity requirement is known.

## Context

The platform already supports local authentication, tenant membership, scoped RBAC, TOTP MFA, hardened sessions/cookies and auditable security-sensitive administration.

The existing AD/LDAP connector is a **read-only evidence connector**. It must not be represented as an interactive login or SSO mechanism.

Customer-ready v1 must avoid two opposite failures:

1. shipping speculative OIDC/SAML code without a real IdP requirement; or
2. coupling authorization to an external identity provider in a way that bypasses tenant membership, roles, organization scopes, MFA/security policy or break-glass administration.

On-prem and air-gapped deployments also mean some customers may use only local authentication while others may require an internal enterprise IdP.

## Decision

### Baseline login

Local username/password plus the platform MFA policy remains a supported first-class authentication path.

### Implementation trigger

Enterprise SSO becomes implementation scope only when the first/target customer provides at least:

- IdP product and deployment model;
- required protocol;
- issuer/entity metadata;
- expected identity claims/attributes;
- account-provisioning model;
- MFA responsibility;
- logout/session expectations;
- availability/offline expectations;
- break-glass policy;
- contractual/security requirements.

Do not select a package or add auth endpoints before these are known.

### Protocol preference

When the target IdP supports modern OIDC, prefer:

**OpenID Connect Authorization Code flow with PKCE**

OIDC should be preferred because it is the default integration target for a new implementation unless the customer environment dictates otherwise.

Implement **SAML 2.0** only when the target IdP or contract requires SAML.

This is a protocol preference, not a statement that every customer must use OIDC.

## Authorization boundary

External authentication proves identity only.

It must **not** automatically grant governance authority.

After successful external authentication, the application must still resolve an explicitly authorized local identity / tenant relationship.

Requirements:

- tenant membership remains server-authoritative;
- organization scopes remain server-authoritative;
- platform roles/permissions remain server-authoritative;
- an unknown external identity must not receive a tenant role by default;
- account linking/provisioning must follow an explicit configured policy;
- role/scope changes remain auditable application actions.

## Provisioning modes

An eventual implementation may support one or more of these, but the customer requirement must choose the policy:

1. **Pre-provisioned accounts** — safest default. Admin creates/authorizes the user first, then links the external identity.
2. **Controlled just-in-time identity creation** — may create a local identity only under an explicit allowlist/domain/claim policy, but must not silently grant privileged tenant roles/scopes.
3. **Directory lifecycle provisioning** — SCIM or equivalent may be considered later when contractually required; it is not implied by SSO.

## MFA policy

Before implementation, define who is authoritative for MFA.

Possible accepted patterns:

- IdP-authenticated sessions satisfy enterprise MFA requirements based on an approved IdP assurance claim/policy; or
- the platform applies an additional local MFA step where required.

Do not silently disable MFA merely because SSO exists.

The chosen assurance policy must be documented for the target deployment.

## Session and logout requirements

An implementation must define and test:

- state/nonce/PKCE validation for OIDC;
- signed assertion / audience / destination / time validation for SAML;
- secure callback handling;
- session fixation prevention;
- local session lifetime and refresh behavior;
- IdP-initiated vs application-initiated login policy;
- local logout behavior;
- single logout only when the target IdP requires and supports it safely;
- disabled/deactivated local membership blocking access even when IdP authentication succeeds.

## On-prem / offline requirement

SSO must not create an undeclared cloud dependency.

For restricted/offline deployments:

- the IdP must be reachable within the approved deployment network; or
- the customer uses the local authentication path.

A cloud-only IdP must not be assumed for an air-gapped installation.

## Break-glass administration

A controlled local emergency administration path must remain available unless the deployment security authority explicitly approves another recovery mechanism.

Break-glass accounts must follow:

- strong local credentials;
- MFA where operationally possible;
- restricted use;
- audit logging;
- protected recovery material;
- documented periodic validation.

An IdP outage must not make authorized recovery impossible.

## Security requirements for eventual implementation

Any SSO implementation must add negative-path regression coverage for:

- cross-tenant account linking;
- issuer/audience/client mix-up;
- state/nonce/PKCE failures;
- replay;
- expired/not-yet-valid tokens/assertions;
- disabled local membership;
- role/scope escalation through claims;
- email/username collision;
- IdP identifier reassignment;
- logout/session invalidation;
- open redirect/callback manipulation;
- sensitive error/log leakage.

It must pass the normal exact-head CI and Release Gate and be included in independent security testing when enabled for production.

## Non-goals

This ADR does not authorize:

- replacing tenant RBAC with IdP groups;
- treating the AD connector as login SSO;
- automatic privileged role assignment from arbitrary claims;
- implementing both OIDC and SAML before a customer needs them;
- removing the local authentication/break-glass path;
- adding a cloud identity dependency to offline deployments.

## Consequences

Positive:

- avoids speculative auth complexity before first-customer requirements are known;
- preserves the platform's tenant/RBAC authority boundary;
- keeps on-prem/offline deployments viable;
- gives engineering a clear default once SSO is required.

Trade-off:

- a customer that requires SSO will still need an implementation batch after its IdP requirements are confirmed.

## Related decisions

- ADR-002 — tenant isolation
- ADR-004 — scoped RBAC
- ADR-005 — TOTP MFA
- #44 — Customer-ready v1 productization program
- #66 — Customer-ready audit / SSO decision reconciliation

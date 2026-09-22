# API Security Contract

Related: #68, #70

This contract defines the minimum security behavior for customer-facing API changes in the GRC platform.

## 1. Tenant boundary

- Resolve the active tenant before accessing tenant-owned domain data.
- Tenant-owned querysets must filter by the active tenant before an identifier is accepted.
- A foreign-tenant identifier must not provide a more informative response than a missing identifier.
- Global/reference content is visible only through the explicit domain visibility rules for that content type.
- Platform-administration endpoints are an explicit exception and require platform-level administrative authorization.

## 2. Organization scope and RBAC

- Frontend visibility is never an authorization control.
- Every domain read/write must enforce the domain permission appropriate to the object and organization scope.
- AI capabilities inherit the permissions of the underlying domain objects. `ai.use` never grants access to Control, Framework, Risk, Evidence or other data that the user could not otherwise read.
- Service-layer authorization is acceptable when the view delegates to that service, but the permission boundary must be covered by negative-path tests.

## 3. Identifier cloaking

For direct identifiers:

- scope the database query first;
- then resolve the object;
- return the module's established not-found response if the identifier is outside the active tenant/scope.

Do not fetch a foreign object first and then return a message that confirms it belongs to another tenant.

## 4. Client-safe errors

- Never return raw stack traces.
- Never persist or return raw provider/transport exceptions when they may contain credentials, secret values or secret-bearing URLs.
- Operational errors may expose an approved error type/status and deliberately allowlisted diagnostics.
- Provider credentials are referenced through approved secret/environment mechanisms and are not persisted in ordinary configuration JSON or embedded in URLs.
- Production remains fail-closed with `DEBUG=0`.

## 5. Audit contract

Consequential security/governance mutations must produce an append-only audit event.

Audit metadata must be minimal and must not contain:
- credentials or secret references;
- raw customer Evidence content;
- raw AI prompts/responses unless explicitly approved by the dedicated AI audit design;
- unrestricted exception text.

High-value examples include role/scope changes, framework lifecycle, workflow configuration/execution, document lifecycle/approvals, connector execution, AI provider configuration and knowledge lifecycle.

## 6. Concurrency / replay contract

State transitions with material governance effects must be safe under duplicate or concurrent execution.

Current patterns:
- Workflow assignment/transition uses `transaction.atomic` plus row locks.
- Document lifecycle serializes consequential version/approval mutations on the Document aggregate root, then locks the relevant Version/Approval rows.
- Data Exchange commit is atomic and its validation token is bound to the exact file bytes, dataset, tenant, user, format and row count.
- Connector collection intentionally creates a distinct ConnectorRun/Evidence record per requested collection; repeated runs are separate auditable observations rather than an idempotent state transition.

Do not remove row locking from lifecycle transitions without replacing it with an equivalent concurrency control.

## 7. Negative-path regression minimum

When a feature crosses a security boundary, tests should include the relevant cases:
- foreign tenant identifier;
- sibling organization scope;
- missing permission / privilege escalation;
- replay of a completed transition;
- secret-bearing provider/transport failure;
- signed-token/file mismatch where signed workflows are used;
- concurrent/replayed lifecycle transitions when duplicate execution is material.

## 8. Change checklist

Before merging a customer-facing endpoint change:

1. identify tenant ownership;
2. identify organization scope;
3. identify required domain permission;
4. identify audit requirement;
5. identify whether the operation is replay/concurrency sensitive;
6. identify secret-bearing inputs/errors;
7. add negative-path coverage;
8. require exact-head CI + Release Gate;
9. verify post-merge CI on `main`.

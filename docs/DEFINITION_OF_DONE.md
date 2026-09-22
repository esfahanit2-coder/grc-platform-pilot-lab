# Definition of Done

A product change is Done only when all applicable conditions are satisfied:

1. Backend/domain behavior is implemented.
2. Tenant and organization scope checks are present.
3. Audit logging is considered and implemented for sensitive changes.
4. API behavior is documented and validation/error semantics are consistent.
5. Required database migrations exist and migration consistency passes.
6. Unit/integration tests cover core behavior and negative authorization paths.
7. Frontend behavior is complete for the agreed scope.
8. Persian RTL and English/LTR behavior are considered where UI is affected.
9. AI behavior remains reviewable/human-in-the-loop for consequential decisions.
10. No secrets, customer data or unlicensed restricted standards content are committed.
11. CI checks pass.
12. Relevant README/ADR/API/roadmap documentation is updated.

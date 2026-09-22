# GRC Platform — Developer Handover (English)

## 1. Start here

Read in this order:

1. `docs/product/README.md`
2. `docs/product/PRODUCT_BRAIN_EN.md`
3. `docs/product/FEATURE_MAP_EN.md`
4. `docs/product/ROADMAP_DETAILED_EN.md`
5. `docs/product/DECISION_LOG.md`
6. `ARCHITECTURE.md`
7. `SECURITY.md`
8. `VALIDATION.md`
9. `RELEASE_BLOCKERS.md`
10. Relevant module tests, issue and PR history.

The code on merged `main` is authoritative for current behavior. Product-brain documents explain intended behavior and rationale.

## 2. Non-negotiable domain rules

Do not violate these without an explicit architecture/product decision:

- Frameworks are versioned content, not framework-specific backend code.
- Common Controls are reusable across multiple framework requirements.
- Control definition and Control Implementation are different objects.
- Assessment results belong to AssessmentItem, not Requirement.
- Risk scores/states are historical RiskEvaluation records, not mutable score fields on Risk.
- Evidence is reusable, scoped, auditable first-class data.
- Tenant and organization scope are enforced server-side.
- AI cannot directly make authoritative risk/compliance/audit decisions.
- Permission filtering happens before RAG retrieval.
- Connectors are read-oriented evidence collectors.
- Restricted standards content requires documented rights.
- On-premise/air-gapped operation must remain possible.

## 3. Repository architecture

- `backend/` — Django/DRF modular-monolith application.
- `frontend/` — Next.js/TypeScript UI.
- `content-packs/` — content-pack examples/specification; never place unauthorized restricted standard text here.
- `docs/` — architecture, operations, product and validation documentation.
- `scripts/` — validation/bootstrap/ops utilities.
- `.github/workflows/` — CI and release gates.

Core backend domains include tenancy, organizations, identity/RBAC, frameworks, controls, assets, risks, assessments, evidence, findings/actions, internal audits/workpapers, documents/reporting, workflows/notifications, connectors and AI gateway/RAG.

## 4. Definition of Done for a code change

A feature is not done because the code compiles.

At minimum:
- tenant/scope authorization is considered;
- important mutations are auditable where appropriate;
- negative paths are tested, not only success paths;
- migrations are clean and `makemigrations --check` passes;
- full Django tests pass against the repository CI database;
- frontend typecheck/lint/production build pass when relevant;
- static/security/release gates remain green;
- documentation/status is updated if the product contract changed.

For PRs, only the latest head SHA is valid evidence. Do not merge based on green runs from an earlier head.

## 5. Real-world proof rule

Some issues intentionally remain open after software implementation:

- authorized live AD/FortiGate/Veeam/Tenable validation;
- clean-host deployment and destructive restore/RPO/RTO proof;
- no-egress local AI proof;
- final authorized ISMS/AFTA/common-control content proof;
- independent penetration test and security sign-off.

Never mark these complete using mocked fixtures or CI-only results.

## 6. AI implementation rule

All AI features must use the provider abstraction and respect data classification/authorization. Useful areas include drafting, summarization, mapping suggestions, remediation suggestions, document/report assistance and RAG.

Consequential outputs must remain suggestions until a human accepts/reviews them. Never make prompt text the only permission boundary. Treat retrieved content as untrusted data.

## 7. Connector implementation rule

Connector code must:
- be read-oriented by default;
- use approved secret references, not literal credentials;
- validate target/network boundaries;
- produce normalized auditable facts/Evidence;
- retain source/time/scope/run/integrity metadata;
- expose diagnosable failures without leaking secrets;
- never mark a control effective or requirement compliant on its own.

## 8. Content-pack rule

A content pack should carry framework metadata, version, requirements, translations/mappings where permitted, provenance and licensing information. Customer-provided restricted text remains customer/tenant scoped unless redistribution rights are explicitly established.

## 9. UI rule

- Persian/RTL and English are product requirements.
- Do not introduce hard-coded production KPIs, fake users or sample risk metrics.
- Use explicit loading, empty and error states.
- UI authorization is supportive; backend authorization is authoritative.
- Clearly label automated/AI/advisory states versus approved authoritative data.

## 10. Current roadmap focus

Pre-RC focus is:
- performance/query/load validation (#20);
- HA/DR and upgrade/rollback reference work (#21);
- offline release bundle and support handbook (#22);
- while real-world proof issues #5/#6/#7/#8 remain open until their required external inputs/environments exist.

Post-v1 product expansion includes TPRM, BCM/BIA, incident management, continuous control monitoring, more connectors, quantitative/FAIR risk, advanced documents, AI governance content, digital-transformation maturity packs and mobile/PWA approvals.

## 11. Change process

Use GitHub as the canonical history:

`Issue -> branch from current main -> implementation/tests/docs -> Draft PR -> latest-head CI + release gate -> review/thread hygiene -> Ready -> squash merge -> post-merge main CI`

Do not lower security/test thresholds merely to make a branch green. Fix the implementation or the test when the test does not reflect runtime reality.

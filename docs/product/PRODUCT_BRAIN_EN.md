# GRC Platform — Product Brain (English)

## 1. Product purpose

GRC Platform is a sovereign, modular, framework-agnostic Governance, Risk & Compliance platform intended for Persian/English enterprise use. It is designed for Iranian regulatory/security environments as well as international standards and management frameworks, without hard-coding any one framework into the application.

Primary framework/content targets discussed for the product include authorized AFTA content, ISMS/ISO/IEC 27001, COBIT, ISO 9001, ISO 31000, digital-transformation maturity models, NIST, CIS, BCM-related material and future AI-governance packs such as ISO 42001 where legally authorized.

The product target is to reach `v0.9.0-pilot` and then `v1.0.0-rc1`, with GitHub as the project source of truth.

## 2. Core product principles

### Frameworks are content, not code
A framework is represented as versioned metadata and requirement content. Adding a new standard/regulation must not require framework-specific backend branches.

### Implement once, comply many
A reusable Common Control can map to many framework requirements. The organization implements the control once through one or more scoped Control Implementations, then reuses evidence/testing across authorized assessments.

### Definition is separate from implementation and assessment
- `Requirement` describes what a framework requires.
- `Control` describes a reusable control definition.
- `ControlImplementation` describes how a real organization/unit implements that control.
- `AssessmentItem` records an assessment result; a result is never stored on the requirement definition itself.

### Risk history is immutable business history
The current risk object represents identity/context. Scores belong in historical `RiskEvaluation` records for inherent/current/residual/target states rather than repeatedly overwriting score fields on Risk.

### Evidence is first-class and reusable
Evidence has source, scope, timestamps, provenance, integrity metadata and links to business objects. One valid evidence object may support several tests/assessments where scope and authorization allow it.

### AI assists; humans decide
AI output is advisory. Consequential suggestions become reviewable `AISuggestion` records or equivalent reviewed workflows. AI must not directly mark a control effective, a requirement compliant, a risk accepted or an audit finding closed.

### Sovereign/on-prem/air-gapped is a first-class deployment mode
Local operation is not an afterthought. The platform supports Docker-based on-premise deployment, local S3-compatible storage, PostgreSQL/pgvector, Redis/Celery and local/private AI providers such as Ollama/vLLM-compatible endpoints. External data egress must be controlled by deployment/customer policy rather than assumed.

## 3. Core architecture

- Backend: Python, Django 5.2 LTS, Django REST Framework.
- Frontend: React/Next.js/TypeScript.
- Database: PostgreSQL 18.
- Semantic retrieval: pgvector with permission-safe retrieval and lexical fallback where appropriate.
- Queue/cache: Redis + Celery.
- Object storage: S3-compatible abstraction.
- AI gateway: provider-independent OpenAI-compatible/Ollama/vLLM/private endpoint model.
- Integration surface: REST APIs are first-class; MCP/integration adapters are a retained direction where they can safely expose approved GRC capabilities.
- Architecture style: modular monolith with explicit application/domain modules.

## 4. Domain chains

```text
Framework -> Version -> Requirement <-> Common Control
Common Control -> Control Implementation -> Evidence -> Control Test
Asset / Process -> Risk -> Risk Evaluation -> Treatment -> Action -> RTP
Framework Version -> Assessment -> Assessment Item -> Evidence -> Finding -> CAPA
Internal Audit -> Workpaper -> Finding -> Action -> Audit Report
Authorized GRC Data -> Permission-safe RAG -> AI -> AISuggestion -> Human Review
```

## 5. Product modules

### Organization, tenancy and identity
Multi-tenant organizations, organization-unit hierarchy, memberships, roles, permissions and organization-scoped RBAC. Backend scope enforcement is mandatory; UI filtering alone is never sufficient. MFA and security policy belong to this layer.

### Framework and content-pack engine
Manages Framework, FrameworkVersion, hierarchical Requirement, translations, import/export, content provenance, licensing metadata and requirement-to-requirement crosswalks. Content packs must preserve legal/source metadata and version history.

### Common controls
Maintains reusable control definitions independent of a specific standard. Controls map to framework requirements and can be duplicated/customized locally without changing global definitions.

### Control implementation and testing
Tracks organization-specific implementation status, owner/operator, implementation description, review dates, effectiveness state, control tests and historical test runs.

### Assets and processes
Provides the organizational/technical context for risk, control, evidence and assurance work. Asset/process relationships should remain reusable across modules.

### Risk management
Supports risk registers, methodology, likelihood/impact scales, historical inherent/current/residual/target evaluations, treatment strategies, actions, appetite/tolerance direction and Risk Treatment Plan outputs. Quantitative/FAIR/Monte Carlo is a post-v1 priority rather than a v1 core requirement.

### Compliance assessment
Creates assessments from locked/versioned framework content. Assessment items preserve snapshots of requirement identity/content and record status, score, maturity/applicability, comments, reviewers, mapped controls, evidence and findings.

### Evidence management
Stores reusable evidence metadata and object-storage references. Evidence may come from users, documents, system connectors or approved automated collection. Connector-produced evidence remains advisory and human-reviewed.

### Findings, NCR and CAPA/actions
Supports findings/non-conformities, severity/status, owners, root cause, due dates, remediation, verification and linked actions/CAPA.

### Internal audit and workpapers
Supports audit engagements, audit scope, workpapers, findings, actions and audit report generation. Audit evidence and findings should integrate with the same shared assurance objects where practical.

### Documents, policies and report factory
Supports document versioning/approval and generated outputs. Named outputs include Statement of Applicability (SoA), Risk Treatment Plan (RTP), audit plans/reports, NCR/CAPA outputs, policies/procedures and management/compliance/risk reports. Earlier product planning explicitly retained DOCX/PDF/XLSX/CSV/JSON export direction and a future Template Designer for configurable report/document layouts. Current implementation is a foundation, not yet the full template-designer target. Policy/procedure generation is an AI-assisted target but human approval remains mandatory.

### Workflow, tasks and notifications
Provides generic assignment, due-date, approval and notification mechanics used by assessments, risks, findings, audits, documents and future modules. A consolidated Task Inbox / Work Center is a retained UX direction so users can see assigned reviews, actions, assessments and approvals across modules rather than hunting through each module separately.

### AI and RAG
AI should help with drafting, summarization, mapping suggestions, evidence analysis, risk/CAPA assistance, remediation suggestions, document/report assistance and retrieval over authorized data. Limited-purpose copilots/agents may orchestrate approved tasks, but they remain constrained by permissions and human review. Permission filtering happens before retrieval. Retrieved evidence/context is treated as untrusted input, not executable instruction.

### API, integrations and MCP direction
The product exposes REST APIs as a primary integration surface. Integration adapters/MCP-style access may be added for approved tools and AI orchestration, but they must reuse the same tenant, organization-scope, audit and permission boundaries as the UI/API. No integration path may become a backdoor around RBAC or human-review rules.

### Connectors
Current pilot connectors are read-oriented AD/LDAP, FortiGate, Veeam and Tenable/Nessus adapters. They collect normalized facts/evidence with auditable scope/source/time and must not autonomously declare compliance or effectiveness.

The GRC platform is not intended to become its own vulnerability scanner. Tenable/Nessus acts as a benchmark/integration target for vulnerability evidence (discovery, credentialed/uncredentialed scan results, CVE/CVSS, configuration/compliance findings, remediation context and historical scan information). Equivalent or stronger scanners should integrate through the same connector abstraction.

### Dashboards, indicators and reporting
Management dashboards must show live tenant-scoped data, not fabricated production-facing demo values. Operational surfaces include connector health/sync history and should expand to assurance/risk/compliance/audit operational views. Configurable indicators/KPIs and management models are a retained product direction, but indicators must be derived from traceable authoritative data.

## 6. User experience requirements

- Persian-first enterprise usability with proper RTL support, while retaining English terminology where helpful.
- Persian and English product documentation for core concepts and developer handover.
- Role/scope-aware experiences; users should see only the work and data their tenant/organization permissions allow.
- Clear distinction between authoritative data, AI suggestions, automated evidence and human approval.
- Strong empty/loading/error states instead of fake sample metrics in production paths.
- Enterprise-oriented UX: traceability, auditability and explainability take priority over decorative complexity.
- A cross-module work/task view should eventually surface reviews, approvals, findings actions and due work in one place.

## 7. Legal/content rules

AFTA/ISO/COBIT or other restricted standard text must not be committed, redistributed or shipped as built-in product content unless appropriate rights exist. Customer-provided/licensed content is tenant-scoped and must retain provenance/licensing metadata. Public classification is not itself a redistribution license.

## 8. Product differentiation retained from earlier research

The product direction was influenced by both Iranian and global GRC products. The retained strategic lessons are:

- Do not build separate applications per standard; build a common framework/control engine.
- Make evidence/control implementation reusable across assessments.
- Combine governance, risk, compliance, audit, documents and actions in one traceable domain model.
- Preserve strong on-premise/air-gapped and local-AI capability rather than assuming SaaS-only operation.
- Support Persian/English/RTL as a product requirement, not a late translation project.
- Keep connectors read-oriented and evidence-focused.
- Use AI for acceleration, not autonomous compliance decisions.
- Treat document/report generation, configurable workflows and operational task management as first-class product outcomes.

## 9. Current product status

Implemented foundations include multi-tenancy/RBAC/MFA, framework engine, common controls, assets, risk management, assessments, evidence, findings/actions, internal audit/workpapers, control testing, documents/reporting, workflow/notifications, AI gateway/RAG, read-only connector implementation, operational dashboard, connector operations UI, CI/security/release gates and pilot deployment foundation.

Real-world proof remains pending for authorized live connectors, clean-host/restore/RPO/RTO/local-AI no-egress operation, independent penetration testing/security sign-off and final authorized content/crosswalk proof.

Pre-RC engineering work continues with repeatable performance/load validation, HA/DR and upgrade/rollback reference work, deterministic offline release packaging and support documentation.

## 10. Explicit post-v1 direction

Post-v1 priorities discussed include TPRM/vendor portal, BCM/BIA, incident management, continuous control monitoring, additional connector packs, quantitative risk/FAIR/Monte Carlo, advanced regulated document generation and Template Designer maturity, AI governance/ISO 42001 content, digital-transformation maturity content and mobile/PWA approval experiences.

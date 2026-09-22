# GRC Platform — Feature Map (English)

Status values: **Implemented**, **Implemented / real-world proof pending**, **In progress**, **Planned pre-v1**, **Content/rights dependent**, **Post-v1**.

| Area | Capability | Why it exists / product intent | Status |
|---|---|---|---|
| Tenancy | Multi-tenant isolation | Separate customer/business data and authorization boundaries | Implemented |
| Organization | Organization-unit hierarchy | Scope controls, risks, assessments, evidence and work by real organizational structure | Implemented |
| Identity | Role/permission + organization-scoped RBAC | Enforce least privilege beyond simple tenant membership | Implemented |
| Identity | MFA / browser security policy | Enterprise authentication and auditable security controls | Implemented |
| Frameworks | Framework / Version / Requirement | Represent standards and regulations as versioned data rather than code | Implemented |
| Frameworks | Hierarchical requirements | Preserve real standard/control-set structures | Implemented |
| Frameworks | Translations | Allow Persian/English content views without duplicating framework logic | Implemented foundation |
| Frameworks | Import/export + provenance/licensing | Safely load customer/licensed content while retaining source/legal metadata | Implemented |
| Frameworks | Requirement crosswalk | Map equivalent/related requirements across frameworks | Implemented foundation; human approval required |
| Content | Authorized AFTA pack workflow | Support tenant-scoped AFTA content without unauthorized redistribution | Implemented / content-rights dependent |
| Content | ISMS/ISO 27001 authorized pack | Real ISMS content and final AFTA/ISMS/internal mapping | Content/rights dependent |
| Controls | Common control library | Reuse one control definition across many framework requirements | Implemented |
| Controls | Control-to-requirement mapping | Realize “implement once, comply many” | Implemented |
| Controls | Control implementation | Record how a control is actually implemented in an org/unit | Implemented |
| Controls | Control testing and historical runs | Separate claimed implementation from tested effectiveness | Implemented |
| Assets | Asset inventory/context | Provide risk/evidence/control context | Implemented |
| Processes | Process context | Business-process relationship to assurance/risk work | Foundation/expansion target |
| Risk | Risk register and categories | Central risk identity/scenario management | Implemented |
| Risk | Methodology/scales | Tenant-defined risk scoring model | Implemented |
| Risk | Inherent/current/residual/target evaluations | Preserve historical score states instead of overwriting Risk | Implemented |
| Risk | Treatment + actions | Convert risk decision into accountable remediation work | Implemented |
| Risk | RTP output | Produce operational Risk Treatment Plan | Implemented |
| Risk | Appetite/tolerance | Governance boundary for risk acceptance/escalation | Product requirement; deeper UX/policy maturity pending |
| Risk | FAIR / Monte Carlo | Advanced quantitative analysis | Post-v1 |
| Assessment | Framework-based assessment creation | Instantiate assessment from locked/versioned requirements | Implemented |
| Assessment | Requirement snapshot | Preserve what was assessed even after later framework changes | Implemented |
| Assessment | Maturity/compliance/status/scoring | Record human-reviewed assessment state | Implemented |
| Assessment | Review/completion controls | Prevent silent autonomous completion | Implemented |
| Evidence | Reusable Evidence object | Collect once and reuse across valid assurance relationships | Implemented |
| Evidence | Scope/source/time/hash/provenance | Make evidence auditable and integrity-aware | Implemented |
| Evidence | Object storage abstraction | Keep binaries outside relational database | Implemented foundation |
| Evidence | Upload quarantine / clean-state gate | Fail closed before potentially unsafe evidence download | Implemented; real malware scanner integration pending |
| Findings | Findings / NCR | Record assurance gaps and non-conformities | Implemented |
| CAPA | Actions / remediation / verification | Drive findings and treatments to closure | Implemented |
| Audit | Internal audit engagements | Formal audit planning/execution domain | Implemented foundation |
| Audit | Workpapers | Preserve audit execution evidence and reasoning | Implemented |
| Audit | Audit reports | Generate formal audit output | Implemented |
| Documents | Document versioning/approval | Controlled policy/procedure/document lifecycle | Implemented foundation |
| Reports | SoA | Generate Statement of Applicability from GRC data | Implemented |
| Reports | RTP | Generate Risk Treatment Plan | Implemented |
| Reports | Management/compliance/risk/audit outputs | Make data consumable by decision-makers | Implemented foundation; UX/report expansion ongoing |
| Reports | DOCX/PDF/XLSX/CSV/JSON output direction | Support operational and management export needs across structured and document formats | Partial foundation; broader format coverage planned |
| Reports | Configurable Template Designer | Let organizations control report/document layouts without hard-coding templates | Product target / post-v1 maturity |
| Workflow | Generic assignment/due date/approval | Shared orchestration across modules | Implemented foundation |
| Workflow | Cross-module Task Inbox / Work Center | Give users one view of assigned reviews, approvals, actions and due work | Retained product/UX target; not yet complete |
| Workflow | Configurable workflow/indicator/model direction | Support organization-specific governance processes and management indicators | Foundation exists; broader configuration planned |
| Notifications | User/system notifications | Surface tasks and events | Implemented foundation |
| Integration | REST API integration surface | Allow approved systems/tools to integrate through the same authorization model | Implemented foundation |
| Integration | MCP/tool adapter direction | Enable approved AI/tool orchestration without bypassing RBAC/audit boundaries | Retained direction / planned |
| AI | Provider-independent AI gateway | Avoid vendor lock-in and support local/private AI | Implemented |
| AI | Ollama/vLLM/OpenAI-compatible providers | Support cloud, private and air-gapped AI paths | Implemented foundation / real-host proof pending |
| AI | AISuggestion / human review | Prevent AI from becoming authoritative business data | Implemented principle and supporting flows |
| RAG | Permission-safe retrieval | Prevent cross-tenant/scope leakage before prompt construction | Implemented foundation |
| RAG | pgvector + lexical fallback | Support semantic retrieval while retaining deterministic fallback | Implemented pilot |
| AI | Drafting/summarization/mapping/remediation suggestions | Accelerate GRC work without removing human responsibility | Implemented foundation / iterative expansion |
| Connectors | AD/LDAP read-only evidence connector | Collect identity/account facts | Implemented / live proof pending |
| Connectors | FortiGate read-only connector | Collect security/network facts | Implemented / live proof pending |
| Connectors | Veeam read-only connector | Collect backup/assurance facts | Implemented / live proof pending |
| Connectors | Tenable/Nessus read-only connector | Collect vulnerability/scanning facts from an external scanner; GRC is not itself the scanner | Implemented / live proof pending |
| Connectors | Normalized Evidence contract | Make provider data reusable and auditable | Implemented |
| Connectors | Health/sync/run history UI | Operate connectors without exposing secrets | Implemented |
| Dashboard | Live tenant-scoped management dashboard | Replace demo data with authoritative operational metrics | Implemented |
| Dashboard | Configurable management indicators/KPIs | Let organizations derive traceable management views from authoritative GRC data | Retained direction / expansion target |
| Security | Auth throttling / TOTP anti-replay / CSRF boundaries | Reduce brute force/replay/browser attack surface | Implemented |
| Security | Cross-tenant IDOR tests | Prove object identifiers do not bypass scope | Implemented |
| Security | Report fetch/SSRF boundaries | Prevent renderer-driven network/local-file exposure | Implemented |
| Security | SAST/secret/container scan/SBOM release gate | Block known high-risk release conditions | Implemented |
| Deployment | Docker pilot composition | Reproducible on-prem deployment foundation | Implemented |
| Deployment | TLS reverse proxy | Production browser/security boundary | Implemented foundation / real-host proof pending |
| Deployment | S3-compatible local storage | Sovereign local file storage | Implemented foundation |
| Deployment | Local AI profile | Optional air-gapped AI runtime | Implemented foundation / no-egress proof pending |
| Deployment | Explicit external-egress policy direction | Avoid assuming customer data may leave an on-prem/air-gapped environment | Product/deployment requirement |
| Operations | Backup/restore tooling | Restore DB/object/config state after failure | Implemented foundation / destructive real drill pending |
| Operations | RPO/RTO measurement | Quantify recoverability instead of assuming it | Real-world proof pending |
| Performance | Query amplification/N+1 regression | Stop list APIs from degrading linearly with row count | In progress (#20) |
| Performance | Repeatable HTTP load harness | Measure p50/p95/error rate on real pilot hardware | In progress (#20) |
| HA/DR | Reference topology | Define availability and disaster-recovery design | Planned pre-v1 (#21) |
| Upgrade | Upgrade/rollback rehearsal | Prove operational reversibility | Planned pre-v1 (#21) |
| Release | Deterministic offline bundle | Install/update in disconnected environments | Planned pre-v1 (#22) |
| Support | Operator/support handbook | Give deployment/support teams an actionable runbook | Planned pre-v1 (#22) |
| Validation | Independent penetration test | External validation before production release | Real-world proof pending (#8) |
| TPRM | Vendor/third-party risk portal | Extend GRC to supplier assurance | Post-v1 |
| BCM | BIA / continuity management | Add resilience/business-impact workflows | Post-v1 |
| Incidents | Incident management | Connect incidents to risks/controls/actions | Post-v1 |
| CCM | Continuous control monitoring | Move from point-in-time assurance to continuous signals | Post-v1 |
| Mobile | PWA/mobile approvals | Lightweight approval/review experience | Post-v1 |

# GRC Platform — Stable Product and Architecture Decision Log

These decisions capture previously agreed constraints and should not be casually reversed. A future change should be documented through an Issue/ADR/PR with explicit migration and product impact.

## D-001 — Frameworks are content, not application code
**Decision:** standards/regulations are versioned data/content packs.  
**Reason:** one platform must support AFTA, ISMS/ISO 27001, COBIT, ISO 9001, ISO 31000, digital-transformation models and future frameworks without creating framework-specific applications.

## D-002 — Common Control Framework is the reuse center
**Decision:** map many requirements to reusable Common Controls.  
**Reason:** implement once, comply many; avoid duplicate control implementations and evidence per framework.

## D-003 — Control definition and Control Implementation are separate
**Decision:** `Control` describes what the control is; `ControlImplementation` describes how/where an organization actually implements it.  
**Reason:** the same control can have different owners, scope, implementation state and evidence across units.

## D-004 — Assessment results never live on Requirement definitions
**Decision:** assessment state belongs to `AssessmentItem`.  
**Reason:** framework content is stable/versioned definition; assessment is historical organization-specific state.

## D-005 — Risk scores are historical evaluations
**Decision:** inherent/current/residual/target values belong in `RiskEvaluation`.  
**Reason:** overwriting one score destroys governance history and auditability.

## D-006 — Evidence is first-class and reusable
**Decision:** Evidence has its own identity, scope, source, provenance and links.  
**Reason:** collect once, reuse where valid; support human uploads and automated connector collection through one assurance model.

## D-007 — Human-in-the-loop is mandatory for consequential AI
**Decision:** AI suggestions are advisory and cannot directly change authoritative compliance/risk/audit decisions.  
**Reason:** governance accountability remains human and auditable.

## D-008 — Permission filtering happens before RAG retrieval
**Decision:** tenant/organization authorization is applied before context reaches the AI pipeline.  
**Reason:** prompt-level instructions are not an acceptable data-isolation boundary.

## D-009 — Retrieved context is untrusted data
**Decision:** RAG evidence/context must never be treated as executable prompt instruction.  
**Reason:** reduce prompt-injection and evidence-content instruction risks.

## D-010 — AI provider abstraction is mandatory
**Decision:** support OpenAI-compatible, Ollama, vLLM/private endpoints behind one gateway.  
**Reason:** avoid vendor lock-in and support cloud/private/air-gapped deployments.

## D-011 — On-premise and air-gapped operation are first-class
**Decision:** local DB/cache/storage/AI and offline release/support remain core architecture requirements.  
**Reason:** target organizations may prohibit internet/cloud dependencies.

## D-012 — Modular monolith first
**Decision:** Django/DRF modular monolith rather than premature microservices.  
**Reason:** preserve domain consistency and delivery velocity while keeping module boundaries explicit.

## D-013 — PostgreSQL is the authoritative transactional store
**Decision:** PostgreSQL 18 is the relational system of record; pgvector extends retrieval rather than replacing the transactional model.  
**Reason:** GRC relationships, auditability and transactions require strong relational semantics.

## D-014 — Files are stored through an S3-compatible abstraction
**Decision:** relational DB stores file metadata/relationships; binaries live in object storage.  
**Reason:** support scalable local/private storage without coupling product logic to one object-store vendor.

## D-015 — Connector collection is read-oriented
**Decision:** AD/LDAP, FortiGate, Veeam and Tenable/Nessus connectors collect facts/evidence and do not make autonomous compliance decisions.  
**Reason:** least privilege, safe pilot operation and clear human authority.

## D-016 — Connector secrets are references, not repository values
**Decision:** configuration stores approved environment-variable/secret-store reference names, never literal credentials in Git/repository content.  
**Reason:** protect credentials and support on-prem secret handling.

## D-017 — Tenant and organization scope must be enforced in backend code
**Decision:** filtering/permission checks are server-side.  
**Reason:** hiding UI elements is not an authorization control.

## D-018 — Persian/English/RTL is a product requirement
**Decision:** bilingual enterprise use is designed into product/docs, not added as a late translation layer.  
**Reason:** target users need Persian-first usability while technical/standard terminology often remains bilingual.

## D-019 — No fabricated production-facing metrics
**Decision:** production UI uses real scoped data with loading/empty/error states.  
**Reason:** sample KPI/risk/profile data undermines operational trust.

## D-020 — Restricted standards content requires authorization
**Decision:** ISO/COBIT/AFTA or other restricted text is not bundled/redistributed without appropriate rights.  
**Reason:** software architecture and product progress must not depend on copyright/license violations.

## D-021 — Customer-provided restricted content is tenant-scoped
**Decision:** customer-supplied content can be processed/imported with provenance but is not automatically converted into redistributable built-in content.  
**Reason:** possession/classification does not establish redistribution rights.

## D-022 — CI/security gates are release controls, not optional checks
**Decision:** runtime tests, static/SAST, secret scan, image vulnerability scan and SBOM/release enforcement remain blocking gates.  
**Reason:** release quality should be mechanically reproducible.

## D-023 — Real-world acceptance cannot be faked
**Decision:** clean-host, live connector, RPO/RTO, no-egress AI, malware workflow, pentest and security sign-off remain open until actually exercised.  
**Reason:** mocked/offline tests prove software behavior but not environmental reality.

## D-024 — Missing customer infrastructure does not block unrelated engineering
**Decision:** continue offline/provider-contract/security/performance/HA/release work while live systems are unavailable.  
**Reason:** environmental blockers should be isolated rather than freezing the roadmap.

## D-025 — Query/load results must be interpreted by environment
**Decision:** CI can prevent query amplification and exercise the load harness, but production capacity/SLO claims require representative hardware and data.  
**Reason:** GitHub runner latency is not a pilot sizing result.

## D-026 — GitHub is the project source of truth
**Decision:** significant changes follow Issue -> Branch -> PR -> latest-head CI/release gates -> merge; tagged releases follow release gating.  
**Reason:** preserve project history, reproducibility and developer handover.

## D-027 — The GRC platform is not a vulnerability scanner
**Decision:** vulnerability discovery/scanning remains the responsibility of dedicated products such as Tenable/Nessus or equivalent systems; GRC consumes normalized findings/evidence through connectors.  
**Reason:** scanner engines, plugins and discovery infrastructure are a different product domain. Keeping the boundary avoids duplicating specialist tools while preserving vulnerability evidence in the GRC traceability model.

## D-028 — Every integration path reuses the same authorization and audit boundaries
**Decision:** REST APIs, future MCP/tool adapters and other integrations must enforce the same tenant, organization-scope, RBAC, audit and human-review rules as the product UI/backend.  
**Reason:** an integration endpoint must never become a privileged backdoor around the domain security model.

## D-029 — External egress is explicit policy, never an assumed capability
**Decision:** on-premise/air-gapped deployments may prohibit all external data transfer; cloud AI or external integrations are enabled only under explicit deployment/customer policy.  
**Reason:** sovereign customers may have organizational or regulatory constraints that make silent/default egress unacceptable.

## D-030 — Documents, reports and templates are first-class product outputs
**Decision:** SoA, RTP, audit outputs, NCR/CAPA, policies/procedures, structured exports and configurable template direction remain part of the product contract rather than ad-hoc utilities. Authoritative status fields must come from GRC data; AI may assist narrative but cannot invent the underlying state.  
**Reason:** the practical value of GRC includes producing controlled, reviewable deliverables for operations, management and auditors.

## D-031 — A cross-module Work Center is a retained UX direction
**Decision:** assignments, reviews, approvals, remediation actions and due work should converge into a unified Task Inbox/Work Center as the UX matures.  
**Reason:** users should not need to visit every module independently to discover accountable work.

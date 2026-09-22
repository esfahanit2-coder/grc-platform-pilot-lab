# GRC Platform — Primary User Journeys (English)

These journeys define the intended end-to-end product experience. They are not a promise that every screen is already equally mature; status is governed by `FEATURE_MAP_EN.md` and the roadmap.

## Persona 1 — GRC / ISMS Program Administrator

**Goal:** establish the organization, load authorized frameworks and create a reusable compliance/control structure.

Journey:
1. Create or enter the tenant and organization-unit hierarchy.
2. Configure memberships, roles and organization scopes.
3. Import an authorized framework/content pack with source/licensing metadata.
4. Review version metadata and lock/activate the appropriate framework version.
5. Create or reuse Common Controls.
6. Map controls to requirements; imported/AI mappings remain unapproved until human review.
7. Assign Control Implementations to real organization units and owners.
8. Launch assessments, audits or risk work using the same reusable control/evidence model.

**Expected outcome:** the organization has one common GRC model rather than isolated spreadsheets per standard.

## Persona 2 — Control Owner / Operator

**Goal:** explain and maintain how a control actually works in a specific part of the organization.

Journey:
1. See assigned Control Implementations within authorized scope.
2. Record implementation description, owner/operator, status and review dates.
3. Attach or link reusable Evidence.
4. Execute or participate in Control Tests.
5. Review historical test runs and findings.
6. Address remediation actions without changing the global control definition.

**Expected outcome:** implementation claims are traceable to scope, evidence and test history.

## Persona 3 — Compliance Assessor / Reviewer

**Goal:** assess one framework/version while reusing existing controls and evidence.

Journey:
1. Create an assessment from a locked/versioned framework.
2. Receive Assessment Items with requirement snapshots.
3. Review mapped controls and existing Evidence.
4. Mark compliance/maturity/applicability and add assessor comments.
5. Request or attach missing Evidence.
6. Raise Findings/NCRs where gaps exist.
7. Reviewer inspects results and completes the assessment only after unresolved/unassessed conditions are handled.
8. Generate management/compliance outputs and, where applicable, SoA.

**Expected outcome:** assessment results are historical, reviewable and independent from the framework definition itself.

## Persona 4 — Risk Owner / Risk Manager

**Goal:** identify, evaluate, treat and monitor risk while preserving score history.

Journey:
1. Register a risk against an asset/process/organization context.
2. Select the tenant risk methodology.
3. Record inherent/current/residual/target evaluations as separate historical RiskEvaluation records.
4. Link existing Control Implementations.
5. Select treatment strategy and create accountable Actions.
6. Track treatment progress and residual-risk evidence.
7. Produce the Risk Treatment Plan (RTP).
8. Use appetite/tolerance governance to support acceptance/escalation as that capability matures.

**Expected outcome:** a defensible risk history exists instead of a mutable single score.

## Persona 5 — Internal Auditor

**Goal:** conduct an audit using shared organizational/control/evidence data rather than rebuilding assurance context.

Journey:
1. Define the audit engagement and scope.
2. Create workpapers and reference relevant controls/requirements/evidence.
3. Perform testing and record audit reasoning.
4. Raise findings with severity, owner, due date and remediation linkage.
5. Track related actions/verification.
6. Generate the audit report.

**Expected outcome:** audit work becomes part of the same GRC traceability chain rather than a separate document silo.

## Persona 6 — Evidence / Infrastructure Operator

**Goal:** supply trustworthy evidence without being able to make compliance decisions.

Journey:
1. Upload approved evidence or configure authorized read-only connectors.
2. For connectors, use environment-variable secret references rather than exposing credentials in the product/repository.
3. Run health checks or read-only syncs.
4. Review ConnectorRun status, normalized dataset/schema metadata and redacted errors.
5. Allow the system to create scoped Evidence with source/time/hash/provenance.
6. Human GRC users decide whether/how that Evidence supports a control test or assessment.

**Expected outcome:** automation reduces collection effort while authority remains with the human assurance process.

## Persona 7 — Document / Policy Owner

**Goal:** create controlled governance documents and reports from structured GRC data.

Journey:
1. Draft or update a controlled document/policy/procedure.
2. Use AI assistance where enabled for drafting/summarization, clearly marked as non-authoritative.
3. Route for review/approval/versioning.
4. Generate structured outputs such as SoA, RTP or audit reports from authoritative data.
5. Retain version and approval history.

**Expected outcome:** generated text accelerates work but does not bypass document governance.

## Persona 8 — Executive / Management Viewer

**Goal:** understand current GRC posture without seeing fabricated or out-of-scope information.

Journey:
1. Open the management dashboard.
2. View live tenant-scoped compliance, residual-risk, findings/actions and assessment indicators.
3. Drill into authorized source records rather than relying on static demo KPIs.
4. Use management reports for review and prioritization.

**Expected outcome:** management sees current, traceable data with clear limitations.

## Persona 9 — AI-assisted GRC Analyst

**Goal:** use AI to accelerate analysis while preserving data boundaries and human authority.

Journey:
1. Ask for help on authorized GRC content/data.
2. Permission filtering occurs before RAG retrieval.
3. Retrieved evidence/context is treated as untrusted data.
4. Provider routing uses the configured OpenAI-compatible/Ollama/vLLM/private endpoint.
5. AI returns draft/suggestion/summary/mapping/remediation assistance.
6. Consequential output is reviewed before it changes authoritative business state.

**Expected outcome:** AI improves speed and consistency without creating autonomous compliance decisions.

## Future journeys retained for post-v1

- Third-party/vendor onboarding and assurance (TPRM).
- Business Impact Analysis and continuity planning (BCM/BIA).
- Incident-to-risk/control/remediation workflow.
- Continuous Control Monitoring review/escalation.
- Mobile/PWA review and approval.

# GRC Platform — Competitive Landscape and Retained Lessons

This document preserves product lessons from earlier Iranian/global GRC research. It is **not** a claim that every vendor feature listed in historical research is still current. Vendor capabilities should be refreshed before procurement or marketing comparisons.

## Iranian products/vendors previously reviewed

Earlier project research discussed the following Iranian GRC products/vendors:

- Sooratec GRC
- RAJA-GRC
- FORTRESS GRC / Farzan Group
- P3GRC
- Amin Raay GRC
- Daya GRC/VA
- HHRN GRC
- FGR
- INFORA
- Eimenyar

RiskBan and Servia were discussed but were not treated as equivalent full-GRC benchmarks in the prior comparison.

A concrete earlier review of Fortress GRC / Farzan identified capabilities such as organizational context, ISMS gap analysis, maturity profiling, form/process builders, information-asset management, risk management, audit, document management and reporting. That research reinforced the need for a broad but integrated domain model rather than a narrow checklist application.

## Global commercial benchmarks previously reviewed

- MetricStream
- Archer
- ServiceNow IRM
- IBM OpenPages
- AuditBoard / Optro
- Diligent
- LogicGate
- Riskonnect
- SAI360
- Resolver
- Workiva
- Mitratech Alyne
- OneTrust
- SAP GRC

## Open-source/community references previously reviewed

- CISO Assistant
- SimpleRisk
- Eramba
- OpenGRC

CISO Assistant was used as a strong functional/reference benchmark in earlier planning. A direct fork was not selected as the product foundation; the project retained its own domain/architecture direction and licensing independence.

## Security/vulnerability benchmark retained

Tenable/Nessus was used as the vulnerability-management benchmark for scanner/integration expectations. Earlier requirements focused on capabilities such as credentialed/uncredentialed scanning, CVE/CVSS, patch/misconfiguration checks, compliance-oriented checks, reporting and updateable plugin/database content. The product does not require the Nessus brand for all future integrations; the design should support equivalent or stronger systems through connector abstractions.

## Product lessons retained from competitor research

### 1. Do not create a separate application per framework
Many products organize experiences around standards/modules. Our domain model instead uses a versioned Framework Engine plus Common Controls so new authorized frameworks become content packs.

### 2. Common Controls are the central reuse mechanism
The product must let one implementation/evidence/testing chain support multiple mapped requirements. This is the core of “implement once, comply many.”

### 3. GRC must connect risk, compliance, audit and remediation
A compliance checklist without risk/treatment/actions/audit/evidence traceability is insufficient. Findings and actions should be shared across assurance workflows where the domain permits.

### 4. Documents and reports are product outputs, not afterthoughts
SoA, RTP, audit reports, management reports, policies/procedures and evidence packages are operational deliverables. Structured GRC data must feed these outputs.

### 5. Persian/English/RTL is a core differentiator for the target market
Localization is not only translation. RTL layout, Persian terminology, bilingual documentation and enterprise usability must remain first-class requirements.

### 6. Sovereign deployment matters
The product deliberately keeps on-premise, private-cloud and air-gapped operation first-class. Local object storage, local AI and offline release/support therefore belong to the product architecture.

### 7. AI should accelerate the analyst, not replace governance
Useful AI areas include drafting, summarization, mapping suggestions, remediation suggestions, report/document assistance and permission-safe RAG. AI does not get authority to accept risk, declare compliance, close findings or approve controls.

### 8. Evidence automation should be connector-driven and read-oriented
Infrastructure connectors should normalize facts into auditable Evidence. They should not become hidden policy engines or autonomous compliance agents.

### 9. Enterprise usability requires operational surfaces
Health, sync history, dashboards, due work, errors, evidence provenance and audit trails matter as much as configuration screens.

### 10. Differentiation is the combination, not one isolated feature
The intended differentiation is the combination of framework-agnostic content packs, reusable common controls/evidence, Iranian/international framework readiness, sovereign deployment, Persian/English UX, human-governed AI/RAG, read-only evidence connectors and end-to-end risk/compliance/audit/document traceability.

## What this document does not claim

- It does not rank vendors.
- It does not assert current pricing, market share or current-version feature parity.
- It does not authorize copying proprietary workflows, UI or content.
- It does not replace a fresh market study before commercial positioning or procurement.

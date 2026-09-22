# Architecture

## Architectural goal

GRC Platform is a sovereign, framework-agnostic, AI-ready governance, risk and compliance platform. Frameworks are content, not application logic; authoritative business decisions remain human-approved; deployments must support SaaS, private cloud, on-premise and air-gapped environments.

## Core chains

```text
Framework -> FrameworkVersion -> Requirement <-> CommonControl
CommonControl -> ControlImplementation -> Evidence -> ControlTest
Asset/Process -> Risk -> RiskEvaluation -> RiskTreatment -> Action -> RTP
FrameworkVersion -> Assessment -> AssessmentItem -> Evidence -> Finding -> CAPA
Audit -> Workpaper -> Finding -> Action -> AuditReport
Authorized GRC Data -> Permission-safe RAG -> AI Gateway -> AISuggestion -> Human Review
```

## Technology

| Layer | Choice |
|---|---|
| Architecture | Modular monolith |
| Backend | Python, Django 5.2 LTS, DRF |
| Frontend | React, Next.js 16, TypeScript |
| Database | PostgreSQL 18 |
| Vector | pgvector |
| Cache/queue | Redis + Celery |
| Object storage | S3-compatible abstraction |
| AI | Provider abstraction: OpenAI-compatible, Ollama, vLLM/private |
| Deployment | Docker; Kubernetes/Helm for enterprise |
| Observability target | OpenTelemetry, Prometheus, Grafana |

## Non-negotiable boundaries

1. Framework content is data, never framework-specific backend branches.
2. Control definition is distinct from organization-specific control implementation.
3. Requirement definition is distinct from assessment result.
4. Risk scores are immutable historical evaluations, not fields overwritten on Risk.
5. AI suggestion is never authoritative until a human accepts it.
6. Permission filtering occurs before RAG retrieval.
7. Files live in object storage; PostgreSQL stores metadata and relationships.
8. Tenant and organization scope are enforced in backend querysets/services, not only in UI.

## Tenancy and security

Each business object is tenant-aware. Scoped RBAC is `User -> Role -> Permissions -> Organization Scope`. Enterprise deployments are designed to add PostgreSQL Row Level Security as a second isolation layer. Sensitive mutations are audited. Browser auth supports HttpOnly JWT cookies with CSRF protection in production.

## Content packs

Standards and regulations are imported as versioned content packs. Packs may contain framework metadata, hierarchical requirements, controls, mappings, scoring, journeys, report templates, translations and licensing metadata. ISO/COBIT copyrighted text must not be bundled without appropriate permission.

## AI architecture

AI calls pass through an orchestrator that performs permission checks, context construction, data-classification policy, optional redaction and provider routing. All consequential results become reviewable `AISuggestion` records. Local/air-gapped AI is supported through Ollama/vLLM-compatible providers.

## Connector architecture

Connectors are read-oriented adapters that collect facts/evidence from external systems. They must not directly mark a control effective or a requirement compliant. Current pilot adapters cover Active Directory/LDAP, Tenable/Nessus, Veeam Enterprise Manager and FortiGate.

## Decision records

See `docs/adr/` and `docs/architecture/` for ADRs covering the modular monolith, tenancy, storage, RBAC, MFA, framework engine, risk/control model, assurance/evidence, audit/document factory, sovereign AI and pilot connectors/RAG.

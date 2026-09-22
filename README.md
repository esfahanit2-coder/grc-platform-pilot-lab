# GRC Platform

A sovereign, framework-agnostic, AI-ready Governance, Risk & Compliance platform designed for Persian/English enterprise use, on-premise and air-gapped deployments.

> **Status:** Pilot Candidate / pre-RC hardening — not yet a production release.

## Why this project exists

The platform is designed to support multiple governance and assurance frameworks on one reusable core instead of building separate applications for each standard. Target content packs include authorized AFTA requirements, ISO/IEC 27001, ISO 31000, ISO 9001, COBIT, NIST, CIS, BCM, AI governance and digital-transformation maturity models.

The central product principle is:

**Frameworks are content, not code.**

A common control can be implemented once and mapped to many requirements. Evidence can be collected once and reused across authorized assessments. AI can assist, but authoritative risk/compliance/audit decisions remain human-reviewed.

## Implemented product core

- Multi-tenant organization model and scoped RBAC.
- TOTP MFA, tenant security policy and auditable security events.
- Framework/version/requirement engine with hierarchical requirements, translation, import/export, licensing metadata and crosswalks.
- Common-control library and organization-specific control implementations.
- Assets/processes, risk methodology, inherent/current/residual/target evaluations, treatments and RTP.
- Compliance assessments, reusable scoped evidence, findings, CAPA/actions and compliance scoring.
- Internal audit, workpapers, control testing and audit findings.
- Document versioning/approval and local report/document generation including SoA/RTP/audit outputs.
- Generic workflows and notifications.
- Provider-independent AI gateway with Ollama/vLLM/OpenAI-compatible options.
- Permission-safe RAG with pgvector pilot support and lexical fallback.
- Human-reviewed AI suggestions.
- Read-only pilot connectors for AD/LDAP, Tenable/Nessus, Veeam and FortiGate.
- Live tenant-scoped management dashboard and connector operations UI.
- Docker/on-premise and air-gapped design path.

## Core architecture

```text
Framework -> Version -> Requirement <-> Common Control
Common Control -> Control Implementation -> Evidence -> Test
Asset/Process -> Risk -> Evaluation -> Treatment -> Action -> RTP
Assessment -> Assessment Item -> Evidence -> Finding -> CAPA
Audit -> Workpaper -> Finding -> Action -> Audit Report
Authorized Data -> Permission-safe RAG -> AI -> Suggestion -> Human Review
```

See [ARCHITECTURE.md](ARCHITECTURE.md) and the ADRs under `docs/`.

## Canonical product knowledge

The bilingual product brain, feature map, detailed roadmap, user journeys, competitive-landscape lessons, AI/connector direction and developer handover are indexed in [`docs/product/README.md`](docs/product/README.md).

Use those documents for product intent and rationale; use merged `main` code for actual current behavior.

## Technology

- Backend: Python / Django 5.2 LTS / Django REST Framework
- Frontend: TypeScript / React / Next.js 16
- Database: PostgreSQL 18
- Semantic retrieval: pgvector
- Queue/cache: Redis + Celery
- Files: S3-compatible object storage abstraction
- Local AI: Ollama / vLLM-compatible endpoints
- Deployment: Docker; Kubernetes/Helm target for enterprise

## Quick start

The frontend lockfile is committed and reproducible npm builds are part of CI/release gating. Tagged/manual releases remain blocked by the configured runtime/security/release gates until all required checks pass.

For development/pilot use:

```bash
cp .env.example .env
docker compose up --build
```

Pilot composition:

```bash
cp .env.pilot.example .env
docker compose -f docker-compose.pilot.yml up --build
```

Local AI profile where supported:

```bash
docker compose --profile local-ai up --build
```

Application endpoints after startup:

- App: `http://localhost:8080`
- Swagger/OpenAPI: `http://localhost:8080/api/v1/docs/`
- Health: `http://localhost:8080/api/v1/health/live`

## Repository map

```text
backend/             Django/DRF application
frontend/            Next.js application
content-packs/       Framework/content pack examples and specification
docs/                Product, API, architecture and pilot documentation
infra/               Infrastructure assets where applicable
scripts/             Validation/bootstrap utilities
.github/workflows/   CI and tagged release gate
```

## Pilot workflow

1. Run CI against PostgreSQL/pgvector and confirm reproducible backend/frontend builds.
2. Bring up a clean pilot environment.
3. Run Golden E2E scenario.
4. Import an authorized framework pack.
5. Run a real assessment with evidence/findings/actions.
6. Generate RTP/SoA/audit outputs.
7. Validate local AI.
8. Validate AD/FortiGate/Veeam/Tenable evidence connectors.
9. Validate backup/restore, RPO/RTO and TLS/cookie hardening.
10. Complete the remaining pre-RC performance, HA/DR, offline-release and independent security validation gates.

Datacenter operators should use [docs/DATACENTER_OPERATIONS.md](docs/DATACENTER_OPERATIONS.md) and the signed offline release path rather than development quick-start commands.

See [ROADMAP.md](ROADMAP.md), [docs/product/ROADMAP_DETAILED_EN.md](docs/product/ROADMAP_DETAILED_EN.md), [docs/product/ROADMAP_DETAILED_FA.md](docs/product/ROADMAP_DETAILED_FA.md), [docs/PILOT_PLAN.md](docs/PILOT_PLAN.md), and [RELEASE_BLOCKERS.md](RELEASE_BLOCKERS.md).

## Licensing and standards content

Do **not** commit or redistribute copyrighted ISO/COBIT/AFTA or other restricted content unless the project has appropriate rights. The platform supports licensed and customer-provided content packs specifically so product code can remain independent of restricted standards text.

## Security

See [SECURITY.md](SECURITY.md). Do not file public issues containing credentials, private customer information or exploitable vulnerability details.

## Project governance

GitHub is the canonical source of truth. Future changes should be Issues -> Branches -> Pull Requests -> CI -> Merge -> tagged Releases. See [GOVERNANCE.md](GOVERNANCE.md).

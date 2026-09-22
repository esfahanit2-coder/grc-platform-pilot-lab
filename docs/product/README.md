# GRC Platform — Canonical Product Knowledge Index

This directory is the canonical product-knowledge layer for the GRC Platform. It consolidates product decisions, architecture intent, roadmap, user journeys, competitor-derived design lessons, implementation status and developer handover context.

## Source-of-truth order

When documents disagree, use this order:

1. Current merged code and migrations on `main` for actual implemented behavior.
2. `ARCHITECTURE.md`, `SECURITY.md`, `ROADMAP.md`, `RELEASE_BLOCKERS.md`, `VALIDATION.md` for current technical/release constraints.
3. This `docs/product/` knowledge set for product intent, bilingual explanations and feature status.
4. Historical issue/PR discussion for rationale and chronology.

No chat transcript is considered canonical after the decision has been consolidated here.

## Canonical documents

| Document | Purpose |
|---|---|
| `PRODUCT_BRAIN_EN.md` | English product brain: vision, domain model, modules, boundaries, outputs and differentiation |
| `PRODUCT_BRAIN_FA.md` | Persian product brain with the same product meaning |
| `FEATURE_MAP_EN.md` | English capability map with status and implementation intent |
| `FEATURE_MAP_FA.md` | Persian capability map with status and implementation intent |
| `ROADMAP_DETAILED_EN.md` | Detailed English roadmap from pilot through RC and post-v1 |
| `ROADMAP_DETAILED_FA.md` | Detailed Persian roadmap |
| `CUSTOMER_READY_V1_AUDIT.md` | Current gap analysis and P0 program from Pilot Candidate to independently deployable customer-ready v1 |
| `USER_JOURNEYS_EN.md` | English primary user journeys and acceptance intent |
| `USER_JOURNEYS_FA.md` | Persian primary user journeys and acceptance intent |
| `COMPETITIVE_LANDSCAPE.md` | Competitor references and the product lessons retained from earlier research |
| `DECISION_LOG.md` | Stable product/architecture decisions that must not be casually reversed |
| `AI_AUTOMATION_DIRECTION.md` | Detailed AI/RAG/automation authority, safety and evaluation direction |
| `CONNECTOR_STRATEGY.md` | Connector contract, security boundaries, evidence model and provider direction |
| `UX_PRODUCT_SPEC_FA.md` | Persian/RTL enterprise UX specification and screen-level principles |
| `DEVELOPER_HANDOVER_EN.md` | English onboarding/handover guide |
| `DEVELOPER_HANDOVER_FA.md` | Persian onboarding/handover guide |

## Status vocabulary

- **Implemented** — present in merged application code and covered by repository validation.
- **Implemented / real-world proof pending** — software exists, but acceptance still depends on authorized infrastructure, clean-host or external validation.
- **In progress** — active branch/issue work exists but is not yet merged/complete.
- **Planned pre-v1** — required before or around v1 RC but not implemented yet.
- **Post-v1** — intentionally deferred beyond the first release candidate.
- **Content/rights dependent** — functionality exists but production content cannot be bundled without authorization/licensing.

## Product north star

A sovereign, framework-agnostic, Persian/English GRC platform where frameworks are versioned content, controls are reusable implementation objects, evidence is reusable first-class data, risk history is preserved, and AI assists without becoming the authoritative decision-maker.

The product must remain deployable on-premise and in air-gapped environments, while supporting private-cloud/SaaS patterns without rewriting the domain model.
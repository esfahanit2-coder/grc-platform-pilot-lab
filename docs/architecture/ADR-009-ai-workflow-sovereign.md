# ADR-009 — Sovereign AI Gateway, Human Approval and Generic Workflow

## Status
Accepted for Sprint 6.

## Context
The platform must support Cloud AI, private endpoints and completely local/air-gapped models without coupling GRC domain code to a single vendor. AI must not silently modify authoritative GRC records. RAG must not bypass tenant or organization-scope permissions.

## Decisions

### 1. Provider abstraction
AI providers are configured per tenant and called through adapters. OpenAI-compatible endpoints, Ollama, vLLM and private endpoints share the same application-level interface.

### 2. Secrets are external
Provider records store a `secret_env_var`, never the API key value itself. Secret injection remains an infrastructure responsibility.

### 3. AI output is advisory
`AIInteraction` records provenance. Domain proposals are stored separately as `AISuggestion`. Accepted suggestions still require normal domain service/permission boundaries before they can be applied.

### 4. Classification gates
Confidential/secret content is blocked from providers that are not explicitly approved for that classification. External prompts receive baseline redaction.

### 5. Permission-before-retrieval
Knowledge retrieval first derives the caller's allowed organization scopes, then searches only authorized chunks. This is mandatory for every future vector implementation as well.

### 6. RAG backend is replaceable
Sprint 6 ships a lexical retriever to keep deployment simple. The retrieval API is isolated so pgvector/Qdrant can be added without changing assistant endpoints.

### 7. Generic workflows
Workflow definitions, states, transitions and instances are generic. Business modules do not get separate hard-coded workflow tables. A transition can demand any existing RBAC permission code.

### 8. Local-first report rendering
The advanced template path uses sandboxed Jinja + local WeasyPrint PDF generation. Cloud document conversion is not required.

### 9. Production browser tokens
The platform supports HttpOnly-cookie JWT mode in addition to Authorization-header JWTs. Production deployments should enable cookie mode behind TLS.

## Consequences
- Air-gapped/local AI deployments are first-class.
- AI interactions are auditable and reviewable.
- No autonomous agent may close findings or accept risks in Sprint 6.
- Semantic vector retrieval remains a post-MVP optimization, not a dependency for the first production candidate.

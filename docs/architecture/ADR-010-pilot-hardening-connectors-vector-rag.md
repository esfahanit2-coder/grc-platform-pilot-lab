# ADR-010 — Pilot hardening: connectors and semantic RAG

## Decision
1. PostgreSQL remains the source of truth and pgvector is enabled for semantic RAG.
2. Knowledge embeddings use a dimensionless `vector` column during pilot to permit multiple embedding models; retrieval filters by model name and actual dimension. No approximate index is introduced until a model is standardized.
3. Connector adapters are read-only. Connector runs produce normal Evidence records and are fully audited.
4. Connector secrets are referenced through environment variable names; raw credentials/tokens are not persisted in connector configuration.
5. Product release is gated on a committed npm lockfile, but ordinary source CI remains runnable before the lock can be generated in a connected environment.

## Rationale
The design avoids a separate vector database, preserves tenant/scope filtering inside PostgreSQL, keeps air-gapped deployment simple, and makes automated evidence collection auditable.

## External protocol notes
- FortiGate REST API supports token authentication and recommends the `Authorization: Bearer` request header.
- Veeam Enterprise Manager uses a logon session and `X-RestSvcSessionId`; current supported API version is available through `v=latest`.
- Tenable scan inventory is read through the public scan API.
- Ollama exposes `POST /api/embed` for local embeddings.

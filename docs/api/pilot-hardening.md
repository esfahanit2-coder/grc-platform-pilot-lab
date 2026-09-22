# Pilot Hardening API

## Semantic RAG
Knowledge chunks now support pgvector embeddings. Use `POST /api/v1/ai/knowledge/{id}/embed/` with an approved provider. The provider configuration may define `configuration.embedding_model`. RAG uses semantic retrieval first in `hybrid` mode and falls back to lexical retrieval.

The vector column intentionally has no fixed dimension during the pilot so different approved embedding models can coexist. Exact cosine search is used; production HNSW indexes should be introduced only after a tenant standardizes an embedding model/dimension.

## Connectors
- `GET/POST /api/v1/connectors/`
- `POST /api/v1/connectors/{id}/health/`
- `POST /api/v1/connectors/{id}/sync/`
- `GET /api/v1/connector-runs/`

Connector secrets are environment-variable references, not stored secret values. All current connector collectors are read-only and create reusable Evidence records.

Supported pilot adapters:
- Active Directory / LDAP
- Tenable-compatible scan inventory
- Veeam Backup Enterprise Manager REST API
- FortiGate REST API read paths

## Golden pilot test
`python manage.py test apps.common.tests.GoldenPilotScenarioTests`

This verifies Framework → Control → Implementation → Asset → Risk → Evaluation → Treatment → Assessment → Evidence → Finding → CAPA → RTP payload.

# Sprint 6 API — AI, RAG, Workflow, Notifications, PDF

## AI providers

- `GET /api/v1/ai/providers/`
- `POST /api/v1/ai/providers/`
- `PATCH /api/v1/ai/providers/{id}/`
- `DELETE /api/v1/ai/providers/{id}/`

Provider configuration stores only the **name of an environment variable** containing the API key. Secret values are not stored in the GRC database.

Supported provider modes:
- `openai_compatible`
- `ollama`
- `vllm` (OpenAI-compatible endpoint)
- `private`
- `mock`

## AI assistants

- `POST /api/v1/ai/assist/risk/`
- `POST /api/v1/ai/assist/control-mapping/`
- `POST /api/v1/ai/assist/document-draft/`
- `POST /api/v1/ai/assist/rag/`

All domain-changing AI output is stored as a pending `AISuggestion`. The AI assistant never finalizes compliance, risk acceptance, finding closure, control effectiveness or document approval.

### Risk example

```json
{
  "risk_id": "<uuid>",
  "provider_id": "<uuid>",
  "classification": "internal"
}
```

### RAG example

```json
{
  "query": "Which open findings relate to privileged access?",
  "classification": "internal"
}
```

The RAG retriever applies tenant and organization-scope filtering **before** retrieval.

## AI suggestions

- `GET /api/v1/ai/suggestions/?status=pending`
- `POST /api/v1/ai/suggestions/{id}/review/`

Review body:

```json
{
  "status": "accepted",
  "comment": "Reviewed by GRC manager"
}
```

Allowed review states:
- `accepted`
- `modified`
- `rejected`

## Knowledge/RAG

- `GET /api/v1/ai/knowledge/`
- `POST /api/v1/ai/knowledge/`
- `DELETE /api/v1/ai/knowledge/{id}/`

Rebuild knowledge from controlled documents, risks and findings:

```bash
python manage.py reindex_ai_knowledge --tenant demo --clear
```

Sprint 6 implements a permission-safe lexical retrieval layer behind an adapter boundary. It is intentionally structured so pgvector/vector retrieval can replace the retriever without changing the AI assistant API.

## Workflow

- `GET /api/v1/workflows/definitions/`
- `POST /api/v1/workflows/definitions/`
- `POST /api/v1/workflows/definitions/{id}/states/`
- `POST /api/v1/workflows/definitions/{id}/transitions/`
- `GET /api/v1/workflows/instances/`
- `POST /api/v1/workflows/instances/start/`
- `POST /api/v1/workflows/instances/{id}/transition/`
- `GET /api/v1/workflows/instances/{id}/events/`

Initial supported generic object types:
- risk
- assessment
- finding
- document
- action
- audit

Workflow transitions can require an existing RBAC permission code such as `risk.treatment.manage`.

## Notifications

- `GET /api/v1/notifications/`
- `GET /api/v1/notifications/?unread=1`
- `GET /api/v1/notifications/summary/`
- `POST /api/v1/notifications/{id}/read/`
- `POST /api/v1/notifications/read-all/`

A Celery Beat task generates overdue-action notifications hourly.

## Template / PDF rendering

- `POST /api/v1/reports/render-template/`

Example:

```json
{
  "template_id": "<uuid>",
  "format": "pdf",
  "context": {
    "title": "Risk Committee Report",
    "period": "1405-06"
  }
}
```

`ReportTemplate.configuration` can contain:

```json
{
  "html_template": "<h1>{{ title }}</h1>",
  "css": "h1 { text-align: right; }"
}
```

Rendering uses a Jinja sandbox. PDF output is local through WeasyPrint and does not require an external cloud service.

## Cookie authentication hardening

When `AUTH_COOKIE_MODE=1`:
- login returns `cookie_auth: true` instead of browser-readable JWTs;
- access and refresh tokens are set as HttpOnly cookies;
- API authentication can read the HttpOnly access cookie;
- refresh can read the protected refresh cookie;
- browser requests use `credentials: include`.

Recommended production flags:

```env
APP_ENV=production
AUTH_COOKIE_MODE=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
```

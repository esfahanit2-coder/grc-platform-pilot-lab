# Sprint 5 API

## Internal audit
- `GET/POST /api/v1/audit-plans/`
- `POST /api/v1/audit-plans/{id}/approve/`
- `GET/POST /api/v1/audits/`
- `GET /api/v1/audits/{id}/report/` — DOCX
- `GET/POST /api/v1/audit-workpapers/`
- `POST /api/v1/audit-workpapers/{id}/review/`
- `POST /api/v1/audit-workpapers/{id}/findings/`

## Control testing
- `GET/POST /api/v1/control-tests/`
- `POST /api/v1/control-tests/{id}/run/`
- `GET /api/v1/control-test-runs/`

## Documents and factory
- `GET/POST /api/v1/documents/`
- `GET/POST /api/v1/document-versions/`
- `POST /api/v1/document-versions/{id}/submit/`
- `GET /api/v1/document-versions/{id}/export/`
- `GET/POST /api/v1/document-approvals/`
- `POST /api/v1/document-approvals/{id}/decide/`
- `GET /api/v1/reports/soa/{assessment_id}/` — DOCX

## Reporting
- `GET /api/v1/dashboard/management/`

All endpoints are tenant- and scope-aware. Formal report generation requires `report.generate`.

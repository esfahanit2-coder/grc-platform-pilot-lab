# Sprint 2 Framework API

All tenant resources require:

```http
Authorization: Bearer <access token>
X-Tenant-ID: <tenant uuid>
```

## Frameworks

- `GET /api/v1/frameworks/`
- `POST /api/v1/frameworks/`
- `GET/PATCH/DELETE /api/v1/frameworks/{id}/`
- `POST /api/v1/frameworks/{id}/duplicate/`
- `POST /api/v1/frameworks/import/?dry_run=true|false`

Global/reference frameworks appear in tenant reads when active, but tenant users cannot mutate them. Duplicate a reference framework to create a tenant-owned editable copy.

## Versions

- `GET /api/v1/framework-versions/?framework={id}`
- `POST /api/v1/framework-versions/`
- `POST /api/v1/framework-versions/{id}/lock/`
- `GET /api/v1/framework-versions/{id}/export/?format=json|xlsx`

Locking generates a canonical SHA-256 checksum and makes the version/requirements immutable.

## Requirements

- `GET /api/v1/requirements/?framework_version={id}`
- `GET /api/v1/requirements/tree/?framework_version={id}`
- `POST/PATCH/DELETE /api/v1/requirements/...`

Translations are submitted as:

```json
{"translations":[{"language":"fa","title":"...","body":"...","guidance":"..."}]}
```

## Crosswalk

- `GET/POST /api/v1/requirement-mappings/`
- `PATCH/DELETE /api/v1/requirement-mappings/{id}/`
- `POST /api/v1/requirement-mappings/{id}/approve/`

Mappings are tenant-owned even when their source/target requirements belong to global reference frameworks.

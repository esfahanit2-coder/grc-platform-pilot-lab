# Sprint 4 API — Assessment, Compliance, Evidence, Findings & CAPA

Sprint 4 adds the assurance loop on top of Framework, Control and Risk domains.

## Assessments

```http
GET/POST /api/v1/assessments/
GET/PATCH/DELETE /api/v1/assessments/<uuid>/
GET /api/v1/assessments/<uuid>/summary/
POST /api/v1/assessments/<uuid>/complete/

GET /api/v1/assessment-items/?assessment=<uuid>
PATCH /api/v1/assessment-items/<uuid>/
POST /api/v1/assessment-items/<uuid>/review/
```

Creating an assessment:

- requires an active FrameworkVersion visible to the tenant;
- locks a tenant-owned FrameworkVersion if it is not already locked;
- creates one AssessmentItem for every assessable Requirement;
- snapshots requirement code/title/body/weight for historical integrity.

Direct reassignment of assessment FrameworkVersion or organization scope is rejected.

### Compliance score

Default status values:

| Status | Score |
|---|---:|
| compliant | 100 |
| partial | 50 |
| non_compliant | 0 |
| compensating_control | 75 |
| not_assessed | excluded |
| not_applicable | excluded |

A numeric AssessmentItem score overrides the default status score. Status scores may be overridden through `assessment.metadata.status_scores`.

## Evidence

```http
GET/POST /api/v1/evidence/
GET/PATCH/DELETE /api/v1/evidence/<uuid>/
GET /api/v1/evidence/<uuid>/download/

GET/POST /api/v1/evidence-links/
DELETE /api/v1/evidence-links/<uuid>/
```

Evidence can be text, URL or a file uploaded through `multipart/form-data` using the `file` field. File payloads are stored through the S3-compatible storage abstraction. SHA-256, size, MIME type and storage key are recorded.

Evidence links currently support:

- assessment
- assessment_item
- control_implementation
- risk
- finding
- action
- requirement

Scoped Evidence cannot be linked across organization-unit boundaries. Tenant-wide Evidence requires whole-tenant `evidence.manage` permission to create/link.

### File-security note

Sprint 4 records `metadata.malware_scan_status=not_scanned` when a file is uploaded. A real scanner adapter and production download gate remain a security-hardening item; see `VALIDATION.md`.

## Findings and CAPA

```http
GET/POST /api/v1/findings/
GET/PATCH/DELETE /api/v1/findings/<uuid>/
POST /api/v1/findings/<uuid>/actions/
POST /api/v1/findings/<uuid>/close/
```

A Finding can reference an AssessmentItem, Requirement, ControlImplementation and/or Risk. When created from an AssessmentItem it inherits the Assessment organization scope and Requirement.

`POST /findings/<id>/actions/` creates a generic GRC Action with `source_type=finding`.

Normal closure is blocked while corrective actions are incomplete. `force=true` is only permitted to users with whole-tenant `finding.close` permission.

Direct PATCH to `status=closed` is rejected; verified closure must use the close action.

## Sprint 4 permissions

- `assessment.view`
- `assessment.manage`
- `assessment.perform`
- `assessment.review`
- `evidence.view`
- `evidence.manage`
- `finding.view`
- `finding.manage`
- `finding.close`

A new system role, `compliance_manager`, is bootstrapped for new and migrated tenants.

# AFTA / ISMS Pilot Content Workflow

This repository must not contain restricted standards text unless explicit product redistribution rights have been documented. Public accessibility alone is not a redistribution license.

## What is safe to ship in the repository

`examples/pilot-isms-security-baseline.json` is original project-authored content. It is the product-owned pilot baseline and includes explicit provenance, scoring/applicability metadata, Persian/English labels, and report hooks. It intentionally does not reproduce ISO, COBIT, AFTA, or other restricted requirements.

## Bringing AFTA / ISMS material into a customer tenant

1. Confirm the customer is entitled to use the source material in the deployment.
2. Copy `templates/customer-provided-restricted-framework.json.example` outside the product repository and populate it only from material the customer is authorized to provide.
3. Record source/version, rights basis, authorization reference, tenant restriction, and provenance in `framework.license_metadata`.
4. Import with `/api/v1/frameworks/import/?dry_run=true` and resolve all validation errors before commit.
5. Commit with `dry_run=false`. The import records a SHA-256 source checksum in framework-version metadata and emits the `framework.import` audit event.
6. Review the imported hierarchy and translations. Lock the version only after content review. Locking creates the canonical version checksum and makes requirements immutable.
7. Never commit the populated restricted pack back to this repository unless separate redistribution/software-integration rights have been verified.

## Common Control Framework crosswalk

The common control is product/tenant-authored content. It can map to requirements from multiple visible frameworks without copying the source requirement text into the control definition.

For a pilot mapping across AFTA, ISMS, and the internal baseline:

1. Import the authorized AFTA framework into the tenant.
2. Import the authorized ISMS framework into the tenant.
3. Import the project-owned internal pilot baseline.
4. Create one original Common Control, for example an organization-specific privileged-access control.
5. Create one `ControlRequirement` mapping from that control to the relevant requirement in each of the three frameworks. Store the mapping method/source and rationale; do not use `approved=true` in the create payload.
6. Human-review each mapping and call `POST /api/v1/control-requirements/{id}/approve/` only after verifying the source and semantic relationship.
7. The approval action is recorded as `control_requirement.approve` with the acting user and timestamp in the immutable application audit trail. Editing a mapping invalidates its approval and requires re-approval.
8. Requirement-to-requirement crosswalks use `RequirementMapping`; those mappings already record `reviewed_by`, `approved_at`, rationale, source type, and `framework_mapping.approve` audit events.

## Pilot acceptance gate

The technical/content-pack gate is satisfied only when all of the following are true:

- the project-owned pilot baseline imports on a clean database without framework-specific backend code;
- its version locks and becomes immutable after review;
- source/licensing provenance is retained;
- scoring/applicability and RTP/SoA/report hooks remain in version metadata;
- real customer-authorized AFTA and ISMS requirements are imported into the tenant;
- at least one original Common Control has reviewed mappings to all three frameworks;
- the approval events are visible in the audit trail;
- no populated restricted AFTA/ISO/COBIT source pack is committed to this repository without verified redistribution rights.

Until customer-authorized AFTA and ISMS source material is available, the final three-framework mapping acceptance item remains intentionally blocked rather than being satisfied with fabricated or copied standards content.

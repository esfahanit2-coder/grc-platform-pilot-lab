# Contributing

## Workflow

`main` is the canonical deployable branch. Work should normally happen on short-lived branches such as `feature/framework-crosswalk`, `fix/tenant-scope-check` or `docs/pilot-runbook`, followed by a pull request.

## Required checks

A pull request is not ready to merge until relevant checks pass:

- Python formatting/static validation.
- Django migration consistency (`makemigrations --check`).
- Django migrations on PostgreSQL.
- Full backend tests.
- Golden GRC E2E tests where applicable.
- Frontend lint and production build.
- Security/dependency checks.

## Domain rules

Do not add framework-specific branches to application code. Do not store assessment status on Requirement, implementation status on common Control, or mutable current scores directly on Risk. Do not let AI write authoritative compliance/risk/audit state without human review.

## Migrations

Every schema change must include migrations and tests. Data migrations must be reversible where practical and validated against representative data.

## API

All product APIs live under `/api/v1/`. New APIs require permission/scope checks, validation, consistent errors and OpenAPI-compatible documentation.

## Documentation

Architecture changes require an ADR. New modules should update README/ROADMAP/API docs where relevant.

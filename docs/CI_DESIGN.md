# CI / Release Gate Design

CI is mandatory before the repository can be considered a release candidate.

## Backend gate

Run against PostgreSQL 18 with pgvector enabled. Required checks:

1. Install backend requirements from the pinned requirements file.
2. Dependency vulnerability audit.
3. `python manage.py makemigrations --check --dry-run`.
4. Apply migrations from an empty database.
5. Full Django test suite.
6. Golden pilot E2E tests.
7. Connector evidence tests.
8. Python compilation/static contract validation.

## Frontend gate

1. A committed `frontend/package-lock.json` is required for a tagged release.
2. Use Node 22 and `npm ci` for release reproducibility.
3. Dependency audit.
4. Lint/type checks.
5. Production build.

## Release gate

A tag matching `v*` must fail if the npm lockfile is missing, runtime tests fail, mutable `latest` container tags are present in release composition, or static contract validation fails.

## Security gate targets

- Python dependency audit.
- npm audit.
- SAST.
- Container scanning.
- SBOM generation.
- Secret scanning.

## Repository status

The GitHub connector used during repository bootstrap could not directly create executable workflow files. CI workflow creation is therefore tracked as an explicit repository issue and remains a release blocker until committed and successfully executed.

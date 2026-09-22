# ADR-005 — TOTP MFA with encrypted secrets

## Decision

Sprint 1 uses TOTP for MFA. Secrets are encrypted at rest with Fernet using `MFA_ENCRYPTION_KEY`; if unset in development, a key is derived from `DJANGO_SECRET_KEY`.

## Production requirement

Set a dedicated stable `MFA_ENCRYPTION_KEY` and protect it in the deployment secret store. Rotating that key requires a controlled migration of stored MFA secrets.

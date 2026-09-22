# ADR-002 — Tenant Isolation

**Status:** Accepted

## Decision

Tenant-scoped business objects carry `tenant_id`. Client-provided tenant selection is accepted only after active membership validation. Application-level filtering is mandatory; PostgreSQL RLS will be added as a defense-in-depth layer for Enterprise deployments.

## Rule

A domain queryset for tenant-owned data must never default to an unscoped `.objects.all()` in request handling code.

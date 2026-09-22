# ADR-001 — Modular Monolith for v1

**Status:** Accepted

## Decision

The v1 platform is a modular monolith with explicit domain boundaries inside one Django deployment.

## Why

GRC transactions frequently cross risk, control, assessment, evidence, audit, and action domains. A modular monolith keeps transactions and on-premise deployment manageable while preserving boundaries that can later be extracted.

## Guardrail

No domain may import another domain's private implementation modules. Cross-domain work should happen through public services/selectors.

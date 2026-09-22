# ADR-003 — S3-Compatible Object Storage Abstraction

**Status:** Accepted

## Decision

The application talks to an internal `ObjectStorage` interface. S3-compatible services are adapters. No business-domain model depends on a specific vendor SDK.

## Consequence

A commercial deployment can replace the development object-storage implementation without changing evidence/document domain code.

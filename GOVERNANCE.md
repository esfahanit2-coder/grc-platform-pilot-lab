# Project Governance

## Source of truth

The canonical private GitHub repository is the source of truth for product code, architecture decisions, issues, pull requests and release artifacts. Chat transcripts and exported ZIP files are working history, not authoritative project state.

## Decision ownership

- Product scope: Product Owner / GRC domain owner.
- Architecture: Technical Lead, recorded via ADR for material changes.
- Security exceptions: explicit documented approval; never silent bypasses.
- Framework/content licensing: product owner plus legal/licensing review before redistribution.

## Change discipline

Material changes should be represented as an Issue, implemented on a branch, reviewed through a Pull Request and merged only after required CI gates pass.

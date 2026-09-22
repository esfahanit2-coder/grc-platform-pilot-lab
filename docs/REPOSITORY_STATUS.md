# Repository Status

## Canonical repository

`esfahanit2-coder/grc-platform` is the canonical private repository and `main` is the canonical source branch.

## Current state

The Pilot Candidate source tree is fully present in GitHub and active development now flows through repository issues, branches, pull requests, CI and release gates. The old one-time import/bootstrap phase is complete and is no longer an active operating model.

The project is currently in **Pilot Candidate / pre-RC hardening**. Core application foundations and the repository-side software preparation for operational UI, performance/load validation, HA/DR and upgrade/rollback, offline release/support, datacenter install/recovery packaging, audit integrity, malware-scanner integration, security validation tooling and clean-host acceptance evidence are implemented.

`ROADMAP.md` is the detailed gate tracker. `RELEASE_BLOCKERS.md` is the concise source for what still prevents v1.0 RC / production rollout.

## Remaining validation and governance boundary

The open release work is intentionally concentrated in things repository CI cannot manufacture or enforce by itself:

- authorized standards/content and crosswalk proof (#5);
- authorized live connector proof (#6);
- real clean-host deployment, TLS, backup/restore, RPO/RTO and no-egress local-AI proof (#7);
- independent security validation, real deployment security evidence and final sign-off (#8);
- target-environment `check --deploy` and organization-approved immutable deployment image pinning;
- repository-admin enforcement of pull-request/status-check protection for `main` (#40).

Do not mark the external validation items complete from mock data, repository fixtures, CI success or documentation alone. Do not treat manual merge discipline as equivalent to an active branch protection/ruleset control.

## Source-of-truth rule

GitHub repository content, issues, pull requests, CI results and releases are authoritative. ZIP exports, local working copies and chat artifacts are not authoritative once their changes have been merged.

All substantive changes should be traceable to an issue or documented task, developed on a branch, validated by the applicable exact-head CI/release gates, and merged through a pull request. Real-world validation evidence should be referenced from the corresponding GitHub issue without committing secrets, customer payloads, private keys or other restricted operational data.

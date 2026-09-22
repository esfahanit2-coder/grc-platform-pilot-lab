# Branching and Releases

## Branches

- `main`: canonical deployable branch. Changes must reach it through a validated pull request once the protection policy below is active.
- `import/pilot-candidate`: historical one-time branch used for importing the existing Pilot Candidate source tree.
- `feature/*`: short-lived product/engineering work.
- `fix/*`: short-lived defect/security remediation work.
- `docs/*`: documentation-only changes when useful.

## Pull requests

Every material code change should be reviewed through a pull request. Required review topics include tenant isolation, organization scope, auditability, migrations, AI human-review boundaries and restricted standards content.

The repository uses exact-head validation: a green workflow result belongs only to the commit SHA that produced it. If the PR head changes, the new head must pass the required checks again before merge.

## `main` protection policy

Issue #40 tracks application of this policy in GitHub repository administration. The policy is intentionally compatible with a single-owner repository: automated release gates are mandatory, but a second human approval is not required merely to satisfy process.

Preferred implementation: an active GitHub **branch ruleset** targeting only `refs/heads/main`. Classic branch protection is acceptable if it enforces the same controls.

Required controls:

1. **Require a pull request before merging.** Direct unvalidated changes to `main` are not an accepted development path.
2. **Require status checks to pass before merging** and require the branch to be up to date with `main` before merge.
3. Configure these exact GitHub Actions check names as required checks:
   - `runtime / backend`
   - `runtime / frontend`
   - `security`
   - `release-ready`
4. **Require conversation resolution before merging.** Unresolved review threads block merge.
5. **Block force pushes** to `main`.
6. **Restrict deletion** of `main`.
7. Do **not** require a human approval count greater than zero while this repository has a single owner. Security-sensitive work still receives explicit review where another authorized reviewer is available, but repository policy must not force self-approval.
8. Keep bypass capability minimal. Prefer no routine bypass actor. If an emergency administrative bypass is retained, restrict it to repository administrators/owners and record the reason, affected SHA and follow-up validation in a tracked issue or incident record. GitHub Actions should not receive a general merge-policy bypass.

### Owner/Admin application steps

In GitHub:

1. Open **Settings → Rules → Rulesets**.
2. Create a new **Branch ruleset** named `main-protection`.
3. Set enforcement to **Active**.
4. Target the default branch or explicitly include `refs/heads/main` only.
5. Enable the controls listed above.
6. Under required status checks, select the four exact checks listed above from GitHub Actions.
7. Enable the option that requires the PR branch to be up to date before merging.
8. Keep required approvals at `0` for the current single-owner operating model.
9. Review the bypass list and remove any actor that does not have a documented operational need.
10. Save the ruleset.

### Verification after applying the rule

Issue #40 may be closed only after all of the following are observed on GitHub:

- `main` is reported as protected by an active rule/ruleset;
- a PR with a pending or failing required check cannot merge;
- moving the PR head requires checks on the new SHA rather than accepting stale green results;
- an unresolved review conversation blocks merge;
- direct force-push and branch deletion are blocked according to policy;
- the configured bypass list matches the documented minimal exception policy.

Repository CI cannot prove these administration controls. The final verification must be performed against the actual GitHub repository configuration.

## Merge discipline

Before merging any PR to `main`:

1. confirm the PR head SHA has not moved since the validated workflow runs;
2. require successful `runtime / backend`, `runtime / frontend`, `security` and `release-ready` checks for that exact head;
3. confirm there are no unresolved review conversations;
4. prefer squash merge unless preserving individual commits is specifically justified;
5. after merge, confirm the push-triggered `main` CI succeeds on the resulting merge/squash commit.

## Release naming

Planned sequence:

- `v0.9.0-pilot`
- `v1.0.0-rc1`
- `v1.0.0`

Tagged release is blocked until runtime CI, frontend lockfile, migration tests, security checks and release reproducibility gates pass, together with the external acceptance evidence tracked by the active release blockers.

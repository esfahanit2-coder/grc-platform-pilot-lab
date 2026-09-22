# Pilot Candidate Import Runbook

The canonical repository currently contains product/governance documentation while the complete 350+ file Pilot Candidate source tree is staged for import.

## Target branch

`import/pilot-candidate`

## Source package

The source package prepared during bootstrap is `grc-platform-github-ready.zip`. It contains the complete Pilot Candidate tree including backend, frontend, migrations, content-pack examples, connector adapters, validation scripts and existing documentation.

## Required import properties

- Preserve paths exactly; do not nest the project under an additional parent directory.
- Do not commit sprint ZIP archives, generated PDF smoke artifacts, `__pycache__`, `.pyc`, local `.env` files, credentials or customer data.
- Preserve `.env.example`, `.env.pilot.example`, Docker compositions, migrations and static validation scripts.
- Generate `frontend/package-lock.json` only from a trusted connected Node environment; do not fabricate it.
- Run static validation before opening the import PR.
- Import into `import/pilot-candidate`, review diff, then merge to `main` after runtime CI passes.

## One-time local import commands

```bash
git clone https://github.com/esfahanhonar-cyber/grc-platform.git
cd grc-platform
git switch import/pilot-candidate

# Copy/extract the GitHub-ready project CONTENTS into this repository root.
# Do not copy the outer parent directory.

git add -A
git status
git commit -m "feat: import GRC pilot candidate codebase"
git push origin import/pilot-candidate
```

After push, open a pull request from `import/pilot-candidate` to `main`, run the full runtime gate, and merge only after the acceptance criteria in the import issue are satisfied.

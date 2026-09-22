#!/usr/bin/env python3
from pathlib import Path
import argparse
import ast
import json
import subprocess
import sys
import yaml

parser = argparse.ArgumentParser(description="Validate repository static contracts.")
parser.add_argument(
    "--skip-typescript",
    action="store_true",
    help="Skip the TypeScript parser check when frontend dependencies are validated in a separate CI job.",
)
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
errors = []

for rel in ["docker-compose.yml", "docker-compose.pilot.yml", ".github/workflows/ci.yml", ".github/workflows/release-gate.yml"]:
    try:
        yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"YAML {rel}: {exc}")

try:
    json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
except Exception as exc:
    errors.append(f"package.json: {exc}")

for rel in ["content-packs/examples/demo-baseline.json", "content-packs/examples/demo-risk-methodology.json", "content-packs/examples/demo-compliance-scoring.json", "content-packs/examples/demo-ai-provider.json", "content-packs/examples/pilot-isms-security-baseline.json", "docs/FINAL_RELEASE_ATTESTATIONS.example.json"]:
    try:
        json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"JSON {rel}: {exc}")

for path in ROOT.glob("backend/**/*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        errors.append(f"Python {path.relative_to(ROOT)}: {exc}")

# TypeScript/TSX syntax check uses the project's own TypeScript dependency.
# Backend CI may skip this parser because the frontend job independently runs
# eslint + the production Next.js build. Release/local full checks should not skip it.
ts_files = list(ROOT.glob("frontend/**/*.ts")) + list(ROOT.glob("frontend/**/*.tsx"))
if ts_files and not args.skip_typescript:
    node_script = r"""
const fs=require('fs'); const ts=require('typescript');
let errors=[];
for (const file of process.argv.slice(1)) {
  const src=fs.readFileSync(file,'utf8');
  const kind=file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf=ts.createSourceFile(file,src,ts.ScriptTarget.ES2022,true,kind);
  for (const d of sf.parseDiagnostics||[]) {
    const msg=ts.flattenDiagnosticMessageText(d.messageText,' ');
    errors.push(`${file}: ${msg}`);
  }
}
if(errors.length){console.error(errors.join('\n'));process.exit(2);}
"""
    try:
        proc = subprocess.run(
            ["node", "-e", node_script, *[str(x) for x in ts_files]],
            cwd=ROOT / "frontend",
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            errors.append("TypeScript/TSX syntax: " + (proc.stderr.strip() or proc.stdout.strip()))
    except Exception as exc:
        errors.append(f"TypeScript/TSX parser failed: {exc}")

required = [
    "backend/config/settings.py",
    "backend/apps/tenancy/middleware.py",
    "backend/apps/tenancy/services.py",
    "backend/apps/tenancy/tests.py",
    "backend/apps/identity/models.py",
    "backend/apps/identity/services.py",
    "backend/apps/identity/tests.py",
    "backend/apps/organizations/views.py",
    "backend/apps/audit/models.py",
    "backend/apps/audit/middleware.py",
    "backend/apps/common/storage.py",
    "frontend/app/page.tsx",
    "frontend/app/login/page.tsx",
    "frontend/app/admin/users/page.tsx",
    "frontend/app/admin/roles/page.tsx",
    "frontend/app/settings/security/page.tsx",
    "backend/apps/frameworks/models.py",
    "backend/apps/frameworks/importers.py",
    "backend/apps/frameworks/views.py",
    "backend/apps/frameworks/tests.py",
    "frontend/app/frameworks/page.tsx",
    "frontend/app/frameworks/import/page.tsx",
    "frontend/app/frameworks/crosswalk/page.tsx",
    "content-packs/spec/v1.md",
    "content-packs/examples/demo-baseline.json",
    "backend/apps/assessments/models.py",
    "backend/apps/assessments/tests.py",
    "backend/apps/evidence/models.py",
    "backend/apps/evidence/tests.py",
    "backend/apps/findings/models.py",
    "backend/apps/findings/tests.py",
    "frontend/app/assessments/page.tsx",
    "frontend/app/assessments/[id]/page.tsx",
    "frontend/app/evidence/page.tsx",
    "frontend/app/findings/page.tsx",
    "docs/api/sprint-4.md",
    "docs/architecture/ADR-007-assurance-evidence-model.md",
    "content-packs/examples/demo-compliance-scoring.json",
    "infra/nginx/default.conf",
    "backend/apps/ai_gateway/models.py",
    "backend/apps/ai_gateway/providers.py",
    "backend/apps/ai_gateway/services.py",
    "backend/apps/workflows/models.py",
    "backend/apps/notifications/models.py",
    "backend/apps/reporting/template_engine.py",
    "frontend/app/ai/page.tsx",
    "frontend/app/ai/suggestions/page.tsx",
    "frontend/app/settings/ai/page.tsx",
    "frontend/app/workflows/page.tsx",
    "frontend/app/notifications/page.tsx",
    "docs/api/sprint-6.md",
    "docs/architecture/ADR-009-ai-workflow-sovereign.md",
    "content-packs/examples/demo-ai-provider.json",
    "backend/apps/connectors/models.py",
    "backend/apps/connectors/clients.py",
    "backend/apps/connectors/services.py",
    "backend/apps/connectors/tests.py",
    "backend/apps/ai_gateway/migrations/0002_semantic_rag_pgvector.py",
    "frontend/app/settings/integrations/page.tsx",
    "docs/api/pilot-hardening.md",
    "docs/architecture/ADR-010-pilot-hardening-connectors-vector-rag.md",
    "docs/PILOT_PLAN.md",
    "content-packs/examples/pilot-isms-security-baseline.json",
    ".github/workflows/release-gate.yml",
    "docker-compose.pilot.yml",
    ".env.pilot.example",
    "backend/apps/ai_gateway/management/commands/reindex_knowledge.py",
    "backend/apps/common/management/commands/pilot_readiness.py",
    "backend/apps/identity/management/commands/bootstrap_datacenter.py",
    "scripts/datacenter-env-validate.py",
    "scripts/datacenter-verify.py",
    "scripts/datacenter-support-bundle.py",
    "scripts/datacenterctl",
    "docs/DATACENTER_OPERATIONS.md",
    "docker-compose.pilot.tls.yml",
    "scripts/final-release-acceptance.py",
    "docs/FINAL_RELEASE_ACCEPTANCE.md",
    "docs/FINAL_RELEASE_ATTESTATIONS.example.json",
]
for rel in required:
    if not (ROOT / rel).exists():
        errors.append(f"Missing: {rel}")

pilot_compose_text = (ROOT / "docker-compose.pilot.yml").read_text(encoding="utf-8")
if "X-Forwarded-Proto':'https'" not in pilot_compose_text:
    errors.append("Pilot backend healthcheck must mark the internal probe as HTTPS through the trusted proxy header")

if (ROOT / ".env").exists():
    errors.append(".env must not be packaged; use .env.example")

if errors:
    print("STATIC CHECK FAILED")
    for err in errors:
        print(" -", err)
    sys.exit(1)

print("STATIC CHECK PASSED")
print("Python files parsed:", sum(1 for _ in ROOT.glob("backend/**/*.py")))
if args.skip_typescript:
    print("TypeScript/TSX parser: skipped (validated by frontend CI job)")
else:
    print("TypeScript/TSX files parsed:", len(ts_files))

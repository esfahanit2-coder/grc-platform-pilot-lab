import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class PilotAcceptanceEvidenceScriptTests(SimpleTestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[3]
        self.script = self.repo_root / "scripts" / "pilot-acceptance-evidence.py"

    def test_self_test_covers_acceptance_and_redaction_invariants(self):
        completed = subprocess.run(
            [sys.executable, str(self.script), "--self-test"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pilot acceptance evidence self-test: PASS", completed.stdout)
        self.assertNotIn("must-not-survive", completed.stdout + completed.stderr)

    def test_help_does_not_require_docker_or_pilot_environment(self):
        completed = subprocess.run(
            [sys.executable, str(self.script), "--help"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("--require-complete", completed.stdout)
        self.assertIn("--manual-observations", completed.stdout)

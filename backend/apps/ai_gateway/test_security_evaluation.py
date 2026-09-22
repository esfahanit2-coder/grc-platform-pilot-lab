import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.tenancy.models import Tenant

from .models import AIProviderConfig
from .providers import AIResponse
from .security_evaluation import (
    ADVERSARIAL_CASES,
    build_case_messages,
    inspect_adversarial_response,
    run_adversarial_evaluation,
)
from .services import RAG_SYSTEM_PROMPT


class SafeProvider:
    def generate(self, messages, *, temperature=0.2, response_format=None):
        return AIResponse(text="The privileged-access review is complete [1].", raw={"ignored": True})


class EchoUserPromptProvider:
    def generate(self, messages, *, temperature=0.2, response_format=None):
        return AIResponse(text=messages[-1]["content"], raw={"ignored": True})


class AISecurityEvaluationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Security Eval Tenant", code="security-eval")
        self.provider = AIProviderConfig.objects.create(
            tenant=self.tenant,
            name="pilot-local",
            provider_type=AIProviderConfig.ProviderType.OLLAMA,
            base_url="http://ollama:11434",
            model_name="pilot-model",
            secret_env_var="SHOULD_NOT_APPEAR_IN_REPORT",
            is_default=True,
        )

    def test_production_rag_prompt_has_non_disclosure_boundary(self):
        self.assertIn("hidden system/developer instructions", RAG_SYSTEM_PROMPT)
        self.assertIn("credentials", RAG_SYSTEM_PROMPT)
        self.assertIn("security canaries", RAG_SYSTEM_PROMPT)

    def test_case_messages_keep_evidence_untrusted_and_add_system_canary(self):
        messages = build_case_messages(
            ADVERSARIAL_CASES[0],
            system_canary="GRC_SYSTEM_TEST",
            evidence_canary="GRC_EVIDENCE_TEST",
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("GRC_SYSTEM_TEST", messages[0]["content"])
        self.assertIn("UNTRUSTED_EVIDENCE_JSON", messages[1]["content"])
        self.assertIn("GRC_EVIDENCE_TEST", messages[1]["content"])

    def test_response_inspection_detects_synthetic_canary_disclosure(self):
        result = inspect_adversarial_response(
            "Unsafe output GRC_EVIDENCE_TEST",
            forbidden_tokens=("GRC_SYSTEM_TEST", "GRC_EVIDENCE_TEST"),
        )
        self.assertFalse(result["automatic_pass"])
        self.assertIn("synthetic_canary_disclosure", result["finding_codes"])
        self.assertEqual(result["leaked_canary_count"], 1)

    @patch("apps.ai_gateway.security_evaluation.provider_for", return_value=SafeProvider())
    def test_real_provider_report_passes_automatic_checks_but_requires_human_review(self, _provider_for):
        report = run_adversarial_evaluation(self.provider)
        self.assertTrue(report["real_model"])
        self.assertTrue(report["execution_complete"])
        self.assertTrue(report["automatic_checks_ok"])
        self.assertTrue(report["human_review_required"])
        self.assertEqual(report["human_review_status"], "pending")
        self.assertEqual(report["case_count"], len(ADVERSARIAL_CASES))

        serialized = json.dumps(report)
        self.assertNotIn("http://ollama:11434", serialized)
        self.assertNotIn("SHOULD_NOT_APPEAR_IN_REPORT", serialized)

    @patch("apps.ai_gateway.security_evaluation.provider_for", return_value=EchoUserPromptProvider())
    def test_prompt_echo_fails_automatic_canary_check(self, _provider_for):
        report = run_adversarial_evaluation(self.provider)
        self.assertFalse(report["automatic_checks_ok"])
        self.assertTrue(
            any("synthetic_canary_disclosure" in row["finding_codes"] for row in report["results"])
        )

    def test_management_command_refuses_mock_as_acceptance_evidence(self):
        self.provider.provider_type = AIProviderConfig.ProviderType.MOCK
        self.provider.save(update_fields=["provider_type"])
        with self.assertRaisesMessage(CommandError, "Refusing to treat the mock provider"):
            call_command(
                "evaluate_ai_security",
                tenant_code=self.tenant.code,
                stdout=StringIO(),
                stderr=StringIO(),
            )

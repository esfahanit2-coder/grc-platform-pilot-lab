from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ai_gateway.models import AIProviderConfig
from apps.ai_gateway.security_evaluation import run_adversarial_evaluation
from apps.ai_gateway.services import select_provider
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = "Run the pre-v1 adversarial AI suite against a configured tenant provider."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", required=True, help="Tenant code whose configured provider will be evaluated.")
        parser.add_argument("--provider-id", help="Optional AIProviderConfig UUID. Defaults to the tenant's configured default provider.")
        parser.add_argument("--json-out", help="Optional path for the machine-readable evaluation report.")
        parser.add_argument(
            "--allow-mock",
            action="store_true",
            help="Permit the mock provider for harness plumbing only. Mock results are never production acceptance evidence.",
        )

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(code=options["tenant_code"]).first()
        if tenant is None:
            raise CommandError(f"Tenant code {options['tenant_code']!r} was not found.")

        provider_cfg = select_provider(tenant, options.get("provider_id"))
        if provider_cfg.provider_type == AIProviderConfig.ProviderType.MOCK and not options.get("allow_mock"):
            raise CommandError(
                "Refusing to treat the mock provider as adversarial model evidence. "
                "Run against the actual pilot provider, or pass --allow-mock only for harness plumbing checks."
            )

        report = run_adversarial_evaluation(provider_cfg)
        payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)

        if options.get("json_out"):
            output = Path(options["json_out"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
            try:
                os.chmod(output, 0o600)
            except OSError:
                pass

        self.stdout.write(payload)

        if not report["execution_complete"]:
            raise CommandError("Adversarial AI evaluation did not complete for every case. Review the JSON evidence.")
        if not report["automatic_checks_ok"]:
            raise CommandError("One or more automatic adversarial AI checks failed. Review the JSON evidence.")

        if report["real_model"]:
            self.stderr.write(
                "Automatic checks passed, but human review remains mandatory before security acceptance."
            )
        else:
            self.stderr.write(
                "Mock-provider plumbing run completed. This report is not valid production security evidence."
            )

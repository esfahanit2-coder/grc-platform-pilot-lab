from __future__ import annotations

import json
import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.audit.verification import (
    build_verification_report,
    verify_all_audit_chains,
    verify_audit_scope,
)


class Command(BaseCommand):
    help = "Verify tamper-evident audit chains and emit operational evidence."

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group()
        scope.add_argument(
            "--tenant-id",
            help="Verify only one tenant audit scope by UUID.",
        )
        scope.add_argument(
            "--global-scope",
            action="store_true",
            help="Verify only the global (tenant-less) audit scope.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit only the versioned JSON report on stdout.",
        )

    def handle(self, *args, **options):
        if options.get("tenant_id"):
            try:
                tenant_id = uuid.UUID(str(options["tenant_id"]))
            except ValueError as exc:
                raise CommandError("--tenant-id must be a valid UUID") from exc
            results = (verify_audit_scope(tenant_id),)
        elif options.get("global_scope"):
            results = (verify_audit_scope(None),)
        else:
            results = verify_all_audit_chains()

        report = build_verification_report(results)
        if options.get("json"):
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            status = "PASS" if report["ok"] else "FAIL"
            self.stdout.write(
                f"Audit integrity {status}: {report['scope_count']} scope(s), "
                f"{report['event_count']} event(s)."
            )
            for result in report["results"]:
                scope_status = "PASS" if result["ok"] else "FAIL"
                self.stdout.write(
                    f"- {result['scope_key']}: {scope_status}; "
                    f"events={result['event_count']}; findings={len(result['findings'])}"
                )
                for finding in result["findings"]:
                    self.stdout.write(
                        f"  {finding['code']}: {finding['message']}"
                    )

        if not report["ok"]:
            raise CommandError("Audit integrity verification failed; preserve the report and investigate before continuing.")

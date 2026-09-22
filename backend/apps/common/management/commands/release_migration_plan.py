from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.common.release_safety import analyze_migration_plan


class Command(BaseCommand):
    help = "Inspect pending release migrations and report rollback blockers without applying them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-reversible",
            action="store_true",
            help="Exit non-zero when the pending plan contains a backward step or irreversible operation.",
        )
        parser.add_argument(
            "--json-out",
            help="Optional path for the machine-readable report. The report never contains credentials.",
        )

    def handle(self, *args, **options):
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        result = analyze_migration_plan(plan)

        report = {
            "schema": "grc-release-migration-plan-v1",
            "database_vendor": connection.vendor,
            "pending_migration_count": len(result.migrations),
            "rollback_safe": result.rollback_safe,
            "migrations": result.migrations,
            "blockers": result.blockers,
        }
        payload = json.dumps(report, indent=2, sort_keys=True)

        if options.get("json_out"):
            output = Path(options["json_out"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        self.stdout.write(payload)

        if options.get("require_reversible") and not result.rollback_safe:
            raise CommandError(
                "Pending migration plan is not rollback-safe. Review the JSON blockers and use the backup-based rollback path."
            )

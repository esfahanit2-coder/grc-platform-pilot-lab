import json

from django.core.management.base import BaseCommand, CommandError

from apps.common.operations import record_operational_signal


class Command(BaseCommand):
    help = "Record a deployment operational signal from an internal maintenance process."

    def add_arguments(self, parser):
        parser.add_argument("key", choices=["backup"])
        parser.add_argument("status", choices=["ok", "warning", "critical"])
        parser.add_argument("--source", required=True)
        parser.add_argument("--metadata", action="append", default=[])

    def handle(self, *args, **options):
        metadata = {}
        for item in options["metadata"]:
            if "=" not in item:
                raise CommandError("--metadata values must be key=value")
            key, value = item.split("=", 1)
            key = key.strip()
            if not key:
                raise CommandError("Metadata key cannot be empty.")
            if key not in {"backup_name", "duration_seconds", "release_consistent_quiesce", "outcome"}:
                raise CommandError(f"Unsupported metadata key: {key}")
            if len(value) > 200:
                raise CommandError("Metadata value is too long.")
            metadata[key] = value
        signal = record_operational_signal(
            options["key"], options["status"], options["source"], metadata=metadata
        )
        self.stdout.write(json.dumps({
            "key": signal.key,
            "status": signal.status,
            "observed_at": signal.observed_at.isoformat(),
        }, sort_keys=True))

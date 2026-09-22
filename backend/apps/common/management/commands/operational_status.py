import json

from django.core.management.base import BaseCommand

from apps.common.operations import build_operational_status


class Command(BaseCommand):
    help = "Print the secret-safe operational deployment status."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        payload = build_operational_status()
        text = json.dumps(payload, default=str, sort_keys=True)
        self.stdout.write(text)

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai_gateway.models import AIProviderConfig
from apps.ai_gateway.providers import provider_for
from apps.common.operations import probe_database, probe_objectstore, probe_redis


class Command(BaseCommand):
    help = "Run non-destructive pilot readiness checks for core dependencies and optional AI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ai-provider-id",
            help="Optional AIProviderConfig UUID to smoke-test generation and embeddings.",
        )
        parser.add_argument(
            "--skip-objectstore",
            action="store_true",
            help="Skip S3/object-storage connectivity check (not valid for final pilot acceptance).",
        )

    def handle(self, *args, **options):
        failures = []
        warnings = []

        try:
            database = probe_database(require_pgvector=True)
            self.stdout.write(f"Database: {database['database_version']}")
            self.stdout.write(self.style.SUCCESS(f"pgvector: {database['pgvector_version']}"))
        except Exception as exc:
            failures.append(f"database readiness failed: {exc}")

        try:
            probe_redis()
            self.stdout.write(self.style.SUCCESS("Redis: reachable"))
        except Exception as exc:
            failures.append(f"Redis readiness failed: {exc}")

        if not options["skip_objectstore"]:
            try:
                probe_objectstore()
                self.stdout.write(self.style.SUCCESS(f"Object storage: bucket {settings.S3_BUCKET!r} reachable"))
            except Exception as exc:
                failures.append(f"object-storage readiness failed: {exc}")

        if getattr(settings, "APP_ENV", "development") == "production":
            if settings.DEBUG:
                failures.append("DEBUG must be disabled in production")
            if not settings.SECURE_SSL_REDIRECT:
                warnings.append("SECURE_SSL_REDIRECT is disabled")
            if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
                failures.append("Secure cookies are required")
            if settings.SECRET_KEY in {"unsafe-dev-key", "change-me-in-production"}:
                failures.append("Production secret key is not configured")
            if not settings.CSRF_TRUSTED_ORIGINS:
                failures.append("CSRF_TRUSTED_ORIGINS is empty in production")

        provider_id = options.get("ai_provider_id")
        if provider_id:
            if not getattr(settings, "AI_ENABLED", True):
                failures.append("AI smoke test requested but AI_ENABLED is false")
            else:
                try:
                    provider_cfg = AIProviderConfig.objects.filter(
                        id=provider_id,
                        is_active=True,
                        deleted_at__isnull=True,
                    ).first()
                    if not provider_cfg:
                        raise CommandError("Requested active AI provider was not found.")
                    provider = provider_for(provider_cfg)
                    response = provider.generate(
                        [{"role": "user", "content": "Reply with the single word OK."}],
                        temperature=0,
                    )
                    if not response.text.strip():
                        raise CommandError("AI provider returned an empty generation.")
                    vectors = provider.embed(["pilot readiness"])
                    if not vectors or not vectors[0]:
                        raise CommandError("AI provider returned no embedding vector.")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"AI provider: {provider_cfg.provider_type}/{provider_cfg.name} generation OK; "
                            f"embedding dimensions={len(vectors[0])}"
                        )
                    )
                except Exception as exc:
                    failures.append(f"AI provider readiness failed: {exc}")
        elif not getattr(settings, "AI_ENABLED", True):
            self.stdout.write(self.style.WARNING("AI: globally disabled by configuration"))
        else:
            warnings.append("AI live smoke test not run; pass --ai-provider-id after configuring a local provider")

        for item in warnings:
            self.stdout.write(self.style.WARNING("WARN: " + item))
        if failures:
            for item in failures:
                self.stdout.write(self.style.ERROR("FAIL: " + item))
            raise CommandError("Pilot readiness checks failed")
        self.stdout.write(self.style.SUCCESS("Pilot readiness checks passed"))

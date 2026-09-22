from django.core.management.base import BaseCommand, CommandError
from apps.ai_gateway.models import AIProviderConfig, KnowledgeChunk
from apps.ai_gateway.services import embed_knowledge_chunk
from apps.tenancy.models import Tenant

class Command(BaseCommand):
    help = "Generate/re-generate embeddings for tenant knowledge chunks using an approved provider."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant code")
        parser.add_argument("--provider", help="AI provider UUID; defaults to tenant default")
        parser.add_argument("--limit", type=int, default=1000)
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        tenant=Tenant.objects.filter(code=options["tenant"],deleted_at__isnull=True).first()
        if not tenant: raise CommandError("Tenant not found")
        providers=AIProviderConfig.objects.filter(tenant=tenant,is_active=True,deleted_at__isnull=True)
        provider=providers.filter(id=options.get("provider")).first() if options.get("provider") else providers.filter(is_default=True).first() or providers.first()
        if not provider: raise CommandError("No active AI provider configured")
        model=str((provider.configuration or {}).get("embedding_model") or provider.model_name)
        qs=KnowledgeChunk.objects.filter(tenant=tenant,deleted_at__isnull=True).order_by("created_at")
        if not options["force"]: qs=qs.exclude(embedding_model=model,embedding__isnull=False)
        total=0
        for chunk in qs[:max(1,options["limit"])]:
            embed_knowledge_chunk(chunk,provider_cfg=provider);total+=1
        self.stdout.write(self.style.SUCCESS(f"Embedded {total} knowledge chunks using {model}"))

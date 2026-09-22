from django.core.management.base import BaseCommand, CommandError
from apps.documents.models import DocumentVersion
from apps.findings.models import Finding
from apps.risks.models import Risk
from apps.tenancy.models import Tenant
from apps.ai_gateway.models import KnowledgeChunk
from apps.ai_gateway.services import upsert_knowledge_chunk

class Command(BaseCommand):
    help='Rebuild tenant-scoped AI knowledge chunks from controlled documents, risks and findings.'
    def add_arguments(self,parser):
        parser.add_argument('--tenant',required=True,help='Tenant code')
        parser.add_argument('--clear',action='store_true')
    def handle(self,*args,**opts):
        tenant=Tenant.objects.filter(code=opts['tenant']).first()
        if not tenant: raise CommandError('Tenant not found.')
        if opts['clear']: KnowledgeChunk.objects.filter(tenant=tenant).delete()
        count=0
        for version in DocumentVersion.objects.filter(document__tenant=tenant,deleted_at__isnull=True).select_related('document__organization_unit','document'):
            if not version.content.strip(): continue
            upsert_knowledge_chunk(tenant=tenant,organization_unit=version.document.organization_unit,source_type='document_version',source_id=version.id,title=f'{version.document.code} — {version.document.title} v{version.version}',content=version.content,classification=(version.document.metadata or {}).get('classification','internal'),metadata={'document_id':str(version.document_id)});count+=1
        for risk in Risk.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related('organization_unit'):
            text='\n'.join(x for x in [risk.title,risk.scenario,risk.cause,risk.consequence] if x)
            if text: upsert_knowledge_chunk(tenant=tenant,organization_unit=risk.organization_unit,source_type='risk',source_id=risk.id,title=f'{risk.code} — {risk.title}',content=text,classification='internal');count+=1
        for finding in Finding.objects.filter(tenant=tenant,deleted_at__isnull=True).select_related('organization_unit'):
            text='\n'.join(x for x in [finding.title,finding.description,finding.root_cause] if x)
            if text: upsert_knowledge_chunk(tenant=tenant,organization_unit=finding.organization_unit,source_type='finding',source_id=finding.id,title=f'Finding — {finding.title}',content=text,classification='internal');count+=1
        self.stdout.write(self.style.SUCCESS(f'Indexed {count} knowledge chunks for {tenant.code}.'))

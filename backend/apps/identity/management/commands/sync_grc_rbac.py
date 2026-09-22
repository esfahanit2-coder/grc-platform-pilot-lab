from django.core.management.base import BaseCommand
from apps.tenancy.models import Tenant
from apps.identity.services import bootstrap_tenant_rbac,ensure_permission_catalog
class Command(BaseCommand):
    help='Synchronize GRC permission catalog and system roles for all tenants.'
    def handle(self,*args,**opts):
        ensure_permission_catalog()
        count=0
        for tenant in Tenant.objects.all(): bootstrap_tenant_rbac(tenant);count+=1
        self.stdout.write(self.style.SUCCESS(f'Synchronized RBAC for {count} tenant(s).'))

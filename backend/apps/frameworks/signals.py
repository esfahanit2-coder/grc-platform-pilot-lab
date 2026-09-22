from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.tenancy.models import Tenant


@receiver(post_migrate)
def refresh_framework_permissions(sender, **kwargs):
    if getattr(sender, "name", "") != "apps.frameworks":
        return
    from apps.identity.services import bootstrap_tenant_rbac, ensure_permission_catalog
    ensure_permission_catalog()
    for tenant in Tenant.objects.all().iterator():
        bootstrap_tenant_rbac(tenant)

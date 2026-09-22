from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.tenancy.models import Tenant, TenantMembership
from .models import Role, UserRoleScope
from .services import bootstrap_tenant_rbac


@receiver(post_save, sender=Tenant)
def bootstrap_roles_for_new_tenant(sender, instance, created, **kwargs):
    if created:
        bootstrap_tenant_rbac(instance)


@receiver(post_save, sender=TenantMembership)
def sync_legacy_admin_membership(sender, instance, created, **kwargs):
    if instance.is_active and instance.role_code == "admin":
        roles = bootstrap_tenant_rbac(instance.tenant)
        UserRoleScope.objects.get_or_create(
            tenant=instance.tenant,
            user=instance.user,
            role=roles["tenant_admin"],
            organization_unit=None,
            defaults={"is_active": True},
        )

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import Tenant
from .integrity import GENESIS_HASH


class AuditIntegrityMutationError(RuntimeError):
    pass


class ImmutableAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AuditIntegrityMutationError("AuditEvent rows are append-only; ORM update is forbidden.")

    def delete(self):
        raise AuditIntegrityMutationError("AuditEvent rows are append-only; ORM delete is forbidden.")


class AuditEventManager(models.Manager.from_queryset(ImmutableAuditEventQuerySet)):
    pass


class AuditChainState(models.Model):
    scope_key = models.CharField(primary_key=True, max_length=80)
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_chain_states",
    )
    sequence = models.PositiveBigIntegerField(default=0)
    last_hash = models.CharField(max_length=64, default=GENESIS_HASH)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Audit chain state"
        verbose_name_plural = "Audit chain states"


class AuditEvent(models.Model):
    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        DENIED = "denied", "Denied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=100)
    category = models.CharField(max_length=64, default="application")
    outcome = models.CharField(max_length=16, choices=Outcome.choices, default=Outcome.SUCCESS)
    object_type = models.CharField(max_length=100)
    object_id = models.UUIDField(null=True, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    old_data = models.JSONField(default=dict, blank=True)
    new_data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    http_method = models.CharField(max_length=12, blank=True)
    path = models.CharField(max_length=500, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    chain_sequence = models.PositiveBigIntegerField(default=0, editable=False)
    previous_hash = models.CharField(max_length=64, default=GENESIS_HASH, editable=False)
    event_hash = models.CharField(max_length=64, blank=True, editable=False)
    integrity_key_id = models.CharField(max_length=64, blank=True, editable=False)

    objects = AuditEventManager()
    # Django's deletion collector must still be able to honor the actor FK's
    # legitimate SET_NULL behavior. Application code should use `objects`;
    # integrity verification detects direct/raw database mutation.
    system_objects = models.Manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditIntegrityMutationError("AuditEvent rows are append-only; instance update is forbidden.")
        if self.chain_sequence < 1 or not self.event_hash or not self.integrity_key_id:
            raise AuditIntegrityMutationError(
                "AuditEvent creation must use record_audit_event() so integrity fields are sealed."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditIntegrityMutationError("AuditEvent rows are append-only; instance delete is forbidden.")

    class Meta:
        ordering = ["-created_at"]
        base_manager_name = "system_objects"
        default_manager_name = "objects"
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["tenant", "actor", "created_at"]),
            models.Index(fields=["tenant", "object_type", "object_id"]),
            models.Index(fields=["tenant", "chain_sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "chain_sequence"],
                condition=models.Q(tenant__isnull=False, chain_sequence__gt=0),
                name="audit_tenant_chain_sequence_unique",
            ),
            models.UniqueConstraint(
                fields=["chain_sequence"],
                condition=models.Q(tenant__isnull=True, chain_sequence__gt=0),
                name="audit_global_chain_sequence_unique",
            ),
        ]

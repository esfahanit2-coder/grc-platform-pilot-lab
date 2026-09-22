from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant


class Notification(UUIDTimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grc_notifications",
    )
    category = models.CharField(max_length=60, default="general")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    severity = models.CharField(max_length=20, default="info")
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "user", "read_at", "created_at"])]


class NotificationDelivery(UUIDTimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    recipient = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_type = models.CharField(max_length=160, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel"],
                name="uq_notification_delivery_channel",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="notif_delivery_retry_idx",
            ),
            models.Index(
                fields=["notification", "status"],
                name="notif_delivery_status_idx",
            ),
        ]

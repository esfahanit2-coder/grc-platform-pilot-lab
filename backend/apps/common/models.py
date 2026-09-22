import uuid
from django.db import models

class UUIDTimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class OperationalSignal(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    key = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    source = models.CharField(max_length=120)
    observed_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["key"]
        indexes = [models.Index(fields=["status", "observed_at"], name="common_ops_status_obs_idx")]

    def __str__(self):
        return f"{self.key}:{self.status}"

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.actions.models import Action
from .models import Finding


def close_finding(finding, user, comment="", force=False):
    open_actions = Action.objects.filter(
        tenant=finding.tenant,
        source_type="finding",
        source_id=finding.id,
        deleted_at__isnull=True,
    ).exclude(status__in=[Action.Status.DONE, Action.Status.CANCELLED])
    if open_actions.exists() and not force:
        raise ValidationError({"actions": "Finding has incomplete corrective actions."})
    finding.status = Finding.Status.CLOSED
    finding.closed_by = user
    finding.closed_at = timezone.now()
    finding.closure_comment = comment or ""
    finding.save(update_fields=["status", "closed_by", "closed_at", "closure_comment", "updated_at"])
    return finding

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tenancy.models import TenantMembership

from .models import Notification, NotificationDelivery


CATEGORY_LABELS = {
    "action_assigned": "اقدام جدید",
    "action_due_soon": "موعد نزدیک اقدام",
    "overdue_action": "اقدام سررسید گذشته",
    "approval_required": "تأیید سند",
    "operational_alert": "هشدار عملیاتی",
}


def email_enabled():
    return bool(getattr(settings, "NOTIFICATION_EMAIL_ENABLED", False))


def notification_email_content(notification):
    category = CATEGORY_LABELS.get(notification.category, "اعلان GRC")
    prefix = str(getattr(settings, "EMAIL_SUBJECT_PREFIX", "[GRC]")).strip()
    subject = f"{prefix} {category}: {notification.title}".strip()
    lines = [
        notification.title,
        "",
        notification.body or "برای مشاهده جزئیات وارد سامانه GRC شوید.",
        "",
        "این پیام از روی اعلان ثبت‌شده در سامانه ارسال شده است.",
    ]
    base_url = str(getattr(settings, "APP_BASE_URL", "") or "").rstrip("/")
    if base_url:
        lines.extend(["", f"سامانه: {base_url}"])
    return subject[:998], "\n".join(lines)


def ensure_email_delivery(notification, *, schedule=True):
    if not email_enabled():
        return None

    current_email = str(notification.user.email or "").strip()
    delivery, _ = NotificationDelivery.objects.get_or_create(
        notification=notification,
        channel=NotificationDelivery.Channel.EMAIL,
        defaults={
            "recipient": current_email,
            "status": (
                NotificationDelivery.Status.PENDING
                if current_email
                else NotificationDelivery.Status.SKIPPED
            ),
            "metadata": {"skip_reason": "missing_email"} if not current_email else {},
        },
    )
    if schedule and delivery.status == NotificationDelivery.Status.PENDING:
        from .tasks import deliver_notification_email

        transaction.on_commit(lambda: deliver_notification_email.delay(str(delivery.id)))
    return delivery


def notify_user(
    *,
    tenant,
    user,
    title,
    body="",
    category="general",
    object_type="",
    object_id=None,
    severity="info",
    metadata=None,
):
    notification = Notification.objects.create(
        tenant=tenant,
        user=user,
        title=title,
        body=body,
        category=category,
        object_type=object_type,
        object_id=object_id,
        severity=severity,
        metadata=metadata or {},
    )
    ensure_email_delivery(notification)
    return notification


def validate_delivery_recipient(delivery):
    notification = delivery.notification
    user = notification.user
    active_member = TenantMembership.objects.filter(
        tenant=notification.tenant,
        user=user,
        is_active=True,
        deleted_at__isnull=True,
    ).exists()
    current_email = str(user.email or "").strip()
    if not user.is_active:
        return None, "inactive_user"
    if not active_member:
        return None, "inactive_membership"
    if not current_email:
        return None, "missing_email"
    return current_email, ""


def mark_delivery_skipped(delivery, reason):
    delivery.status = NotificationDelivery.Status.SKIPPED
    delivery.last_error_type = ""
    delivery.next_attempt_at = None
    delivery.metadata = {**(delivery.metadata or {}), "skip_reason": reason}
    delivery.save(
        update_fields=[
            "status",
            "last_error_type",
            "next_attempt_at",
            "metadata",
            "updated_at",
        ]
    )
    return delivery


def mark_read(notification):
    if not notification.read_at:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
    return notification

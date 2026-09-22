from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from apps.actions.models import Action
from apps.common.operations import build_operational_status, record_operational_signal
from apps.identity.services import has_whole_tenant_permission
from apps.tenancy.models import Tenant, TenantMembership

from .models import Notification, NotificationDelivery
from .services import (
    mark_delivery_skipped,
    notification_email_content,
    notify_user,
    validate_delivery_recipient,
)


def _delivery_retry_seconds():
    return max(60, int(getattr(settings, "NOTIFICATION_EMAIL_RETRY_SECONDS", 300)))


def _delivery_max_attempts():
    return max(1, int(getattr(settings, "NOTIFICATION_EMAIL_MAX_ATTEMPTS", 5)))


@shared_task(name="apps.notifications.tasks.deliver_notification_email")
def deliver_notification_email(delivery_id):
    with transaction.atomic():
        delivery = (
            NotificationDelivery.objects.select_for_update()
            .select_related("notification__tenant", "notification__user")
            .filter(id=delivery_id, deleted_at__isnull=True)
            .first()
        )
        if not delivery:
            return {"status": "missing"}
        if delivery.status in {
            NotificationDelivery.Status.SENT,
            NotificationDelivery.Status.SKIPPED,
        }:
            return {"status": delivery.status}

        recipient, skip_reason = validate_delivery_recipient(delivery)
        if skip_reason:
            mark_delivery_skipped(delivery, skip_reason)
            return {"status": "skipped", "reason": skip_reason}

        delivery.recipient = recipient
        delivery.status = NotificationDelivery.Status.SENDING
        delivery.attempt_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.next_attempt_at = None
        delivery.last_error_type = ""
        delivery.save(
            update_fields=[
                "recipient",
                "status",
                "attempt_count",
                "last_attempt_at",
                "next_attempt_at",
                "last_error_type",
                "updated_at",
            ]
        )

    notification = delivery.notification
    subject, body = notification_email_content(notification)
    message_id = f"<grc-notification-{delivery.id}@local>"

    try:
        accepted = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient],
            headers={"Message-ID": message_id},
        ).send(fail_silently=False)
        if accepted != 1:
            raise RuntimeError("Email backend did not accept exactly one message.")
    except Exception as exc:
        now = timezone.now()
        with transaction.atomic():
            current = NotificationDelivery.objects.select_for_update().get(id=delivery.id)
            current.status = NotificationDelivery.Status.FAILED
            current.last_error_type = type(exc).__name__
            current.next_attempt_at = (
                now + timedelta(seconds=_delivery_retry_seconds())
                if current.attempt_count < _delivery_max_attempts()
                else None
            )
            current.save(
                update_fields=[
                    "status",
                    "last_error_type",
                    "next_attempt_at",
                    "updated_at",
                ]
            )
        record_operational_signal(
            "notification-email",
            "warning",
            "smtp-delivery",
            metadata={"outcome": "failed", "error_type": type(exc).__name__},
        )
        return {"status": "failed", "error_type": type(exc).__name__}

    with transaction.atomic():
        current = NotificationDelivery.objects.select_for_update().get(id=delivery.id)
        current.status = NotificationDelivery.Status.SENT
        current.sent_at = timezone.now()
        current.next_attempt_at = None
        current.last_error_type = ""
        current.provider_message_id = message_id
        current.save(
            update_fields=[
                "status",
                "sent_at",
                "next_attempt_at",
                "last_error_type",
                "provider_message_id",
                "updated_at",
            ]
        )
    record_operational_signal(
        "notification-email",
        "ok",
        "smtp-delivery",
        metadata={"outcome": "success"},
    )
    return {"status": "sent"}


@shared_task(name="apps.notifications.tasks.retry_failed_email_deliveries")
def retry_failed_email_deliveries():
    if not getattr(settings, "NOTIFICATION_EMAIL_ENABLED", False):
        return 0
    now = timezone.now()
    ids = list(
        NotificationDelivery.objects.filter(
            status=NotificationDelivery.Status.FAILED,
            next_attempt_at__isnull=False,
            next_attempt_at__lte=now,
            attempt_count__lt=_delivery_max_attempts(),
            deleted_at__isnull=True,
        )
        .order_by("next_attempt_at")
        .values_list("id", flat=True)[:200]
    )
    for delivery_id in ids:
        deliver_notification_email.delay(str(delivery_id))
    return len(ids)


@shared_task(name="apps.notifications.tasks.create_due_action_notifications")
def create_due_action_notifications():
    today = timezone.localdate()
    days = max(1, int(getattr(settings, "NOTIFICATION_DUE_SOON_DAYS", 3)))
    end = today + timedelta(days=days)
    created = 0
    actions = (
        Action.objects.filter(
            deleted_at__isnull=True,
            due_date__gte=today,
            due_date__lte=end,
        )
        .exclude(status__in=[Action.Status.DONE, Action.Status.CANCELLED])
        .select_related("owner", "tenant")
    )
    for action in actions:
        exists = Notification.objects.filter(
            tenant=action.tenant,
            user=action.owner,
            category="action_due_soon",
            object_type="action",
            object_id=action.id,
            created_at__date=today,
        ).exists()
        if not exists:
            notify_user(
                tenant=action.tenant,
                user=action.owner,
                category="action_due_soon",
                title=f"موعد اقدام نزدیک است: {action.title}",
                body=f"تاریخ سررسید: {action.due_date}",
                object_type="action",
                object_id=action.id,
                severity="warning",
            )
            created += 1
    return created


@shared_task(name="apps.notifications.tasks.create_overdue_action_notifications")
def create_overdue_action_notifications():
    today = timezone.localdate()
    created = 0
    actions = (
        Action.objects.filter(
            deleted_at__isnull=True,
            due_date__lt=today,
        )
        .exclude(status__in=[Action.Status.DONE, Action.Status.CANCELLED])
        .select_related("owner", "tenant")
    )
    for action in actions:
        exists = Notification.objects.filter(
            tenant=action.tenant,
            user=action.owner,
            category="overdue_action",
            object_type="action",
            object_id=action.id,
            created_at__date=today,
        ).exists()
        if not exists:
            notify_user(
                tenant=action.tenant,
                user=action.owner,
                category="overdue_action",
                title=f"اقدام از موعد گذشته است: {action.title}",
                body=f"تاریخ سررسید: {action.due_date}",
                object_type="action",
                object_id=action.id,
                severity="warning",
            )
            created += 1
    return created


@shared_task(name="apps.notifications.tasks.create_operational_alert_notifications")
def create_operational_alert_notifications():
    status = build_operational_status()
    overall = status.get("overall_status")
    if overall == "healthy":
        return 0

    component_names = sorted(
        name
        for name, component in (status.get("components") or {}).items()
        if (component or {}).get("status") not in {"ok"}
    )
    today = timezone.localdate()
    created = 0
    for tenant in Tenant.objects.filter(status="active", deleted_at__isnull=True):
        memberships = TenantMembership.objects.filter(
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True,
            user__is_active=True,
        ).select_related("user")
        for membership in memberships:
            if not has_whole_tenant_permission(
                membership.user, tenant, "security.view"
            ):
                continue
            exists = Notification.objects.filter(
                tenant=tenant,
                user=membership.user,
                category="operational_alert",
                metadata__overall_status=overall,
                created_at__date=today,
            ).exists()
            if exists:
                continue
            notify_user(
                tenant=tenant,
                user=membership.user,
                category="operational_alert",
                title=f"وضعیت عملیاتی سامانه: {overall}",
                body=(
                    "مولفه‌های نیازمند بررسی: "
                    + (", ".join(component_names) if component_names else "نامشخص")
                ),
                severity="warning" if overall == "degraded" else "critical",
                metadata={"overall_status": overall, "components": component_names},
            )
            created += 1
    return created

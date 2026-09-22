from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership

from .models import Notification, NotificationDelivery
from .services import ensure_email_delivery, notify_user
from .tasks import (
    create_due_action_notifications,
    deliver_notification_email,
)


User = get_user_model()


class NotificationDeliveryTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="notification-admin",
            email="admin@example.internal",
            password="StrongPassword123!",
        )
        self.user = User.objects.create_user(
            username="notification-user",
            email="user@example.internal",
            password="StrongPassword123!",
        )
        self.tenant = Tenant.objects.create(
            name="Notification Tenant",
            code="notification-tenant",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.admin,
            role_code="admin",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role_code="member",
        )
        bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            code="HQ",
            name="HQ",
        )

    def auth(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    @override_settings(
        NOTIFICATION_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="grc@example.internal",
    )
    def test_email_delivery_uses_authoritative_notification_and_marks_sent(self):
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=self.user,
            category="action_assigned",
            title="Assigned action",
            body="Authoritative notification body",
        )
        delivery = ensure_email_delivery(notification, schedule=False)
        result = deliver_notification_email(str(delivery.id))

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.recipient, self.user.email)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Authoritative notification body", mail.outbox[0].body)

    @override_settings(
        NOTIFICATION_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_delivery_rechecks_active_tenant_membership_before_sending(self):
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=self.user,
            title="Membership check",
        )
        delivery = ensure_email_delivery(notification, schedule=False)
        TenantMembership.objects.filter(
            tenant=self.tenant,
            user=self.user,
        ).update(is_active=False)

        result = deliver_notification_email(str(delivery.id))
        delivery.refresh_from_db()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(delivery.status, NotificationDelivery.Status.SKIPPED)
        self.assertEqual(delivery.metadata["skip_reason"], "inactive_membership")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        NOTIFICATION_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        NOTIFICATION_EMAIL_RETRY_SECONDS=60,
        NOTIFICATION_EMAIL_MAX_ATTEMPTS=3,
    )
    def test_delivery_failure_persists_only_error_type(self):
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=self.user,
            title="Failure check",
        )
        delivery = ensure_email_delivery(notification, schedule=False)

        with patch(
            "apps.notifications.tasks.EmailMessage.send",
            side_effect=RuntimeError(
                "smtp://user:super-secret@private-mail.example/internal"
            ),
        ):
            result = deliver_notification_email(str(delivery.id))

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(delivery.last_error_type, "RuntimeError")
        self.assertIsNotNone(delivery.next_attempt_at)
        rendered = str(delivery.metadata) + delivery.last_error_type
        self.assertNotIn("super-secret", rendered)
        self.assertNotIn("private-mail.example", rendered)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True)
    @patch("apps.notifications.tasks.deliver_notification_email.delay")
    def test_notify_user_creates_one_email_delivery_without_duplicate_business_state(
        self, delay
    ):
        with self.captureOnCommitCallbacks(execute=True):
            notification = notify_user(
                tenant=self.tenant,
                user=self.user,
                category="action_assigned",
                title="Assigned",
                object_type="action",
            )
        self.assertEqual(Notification.objects.filter(id=notification.id).count(), 1)
        self.assertEqual(notification.deliveries.count(), 1)
        delay.assert_called_once()

    @override_settings(NOTIFICATION_EMAIL_ENABLED=False, NOTIFICATION_DUE_SOON_DAYS=3)
    def test_due_soon_task_references_action_and_deduplicates_daily(self):
        action = Action.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            title="Due soon",
            owner=self.user,
            due_date=timezone.localdate(),
        )
        first = create_due_action_notifications()
        second = create_due_action_notifications()

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        notification = Notification.objects.get(
            tenant=self.tenant,
            user=self.user,
            category="action_due_soon",
            object_id=action.id,
        )
        self.assertEqual(notification.object_type, "action")

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True)
    @patch("apps.notifications.tasks.deliver_notification_email.delay")
    def test_operator_can_retry_failed_delivery_but_user_cannot_cross_boundary(
        self, delay
    ):
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=self.user,
            title="Retry me",
        )
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            recipient=self.user.email,
            status=NotificationDelivery.Status.FAILED,
            attempt_count=1,
            last_error_type="RuntimeError",
        )

        self.auth(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/notification-deliveries/{delivery.id}/retry/"
            )
        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.PENDING)
        delay.assert_called_once_with(str(delivery.id))

        self.auth(self.user)
        denied = self.client.get("/api/v1/notification-deliveries/")
        self.assertEqual(denied.status_code, 403)

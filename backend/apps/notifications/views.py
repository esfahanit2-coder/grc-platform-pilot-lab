from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.identity.services import require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request

from .models import Notification, NotificationDelivery
from .serializers import NotificationDeliverySerializer, NotificationSerializer
from .services import mark_read


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def _tenant(self):
        return resolve_tenant_for_request(self.request)

    def get_queryset(self):
        qs = Notification.objects.filter(
            tenant=self._tenant(),
            user=self.request.user,
            deleted_at__isnull=True,
        )
        if self.request.query_params.get("unread") in {"1", "true"}:
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        return Response(self.get_serializer(mark_read(self.get_object())).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).update(
            read_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response({"updated": count})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        return Response(
            {"unread": self.get_queryset().filter(read_at__isnull=True).count()}
        )


class NotificationDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationDeliverySerializer

    def _tenant(self):
        tenant = resolve_tenant_for_request(self.request)
        require_whole_tenant_permission(self.request.user, tenant, "security.view")
        return tenant

    def get_queryset(self):
        tenant = self._tenant()
        qs = NotificationDelivery.objects.filter(
            notification__tenant=tenant,
            deleted_at__isnull=True,
        ).select_related("notification", "notification__user")
        status_value = self.request.query_params.get("status")
        if status_value:
            qs = qs.filter(status=status_value)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        delivery = self.get_object()
        if delivery.status != NotificationDelivery.Status.FAILED:
            raise ValidationError("Only failed email deliveries can be retried.")

        with transaction.atomic():
            locked = NotificationDelivery.objects.select_for_update().get(id=delivery.id)
            locked.status = NotificationDelivery.Status.PENDING
            locked.next_attempt_at = timezone.now()
            locked.last_error_type = ""
            locked.save(
                update_fields=[
                    "status",
                    "next_attempt_at",
                    "last_error_type",
                    "updated_at",
                ]
            )
            from .tasks import deliver_notification_email

            transaction.on_commit(
                lambda: deliver_notification_email.delay(str(locked.id))
            )

        return Response(self.get_serializer(locked).data)

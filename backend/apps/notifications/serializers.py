from rest_framework import serializers

from .models import Notification, NotificationDelivery


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "category",
            "title",
            "body",
            "object_type",
            "object_id",
            "severity",
            "read_at",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class NotificationDeliverySerializer(serializers.ModelSerializer):
    notification_title = serializers.CharField(source="notification.title", read_only=True)
    notification_category = serializers.CharField(source="notification.category", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = [
            "id",
            "notification",
            "notification_title",
            "notification_category",
            "channel",
            "recipient",
            "status",
            "attempt_count",
            "last_attempt_at",
            "next_attempt_at",
            "sent_at",
            "last_error_type",
            "provider_message_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

from rest_framework import serializers

from apps.tenant.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient_email",
            "recipient_user_id",
            "title",
            "message",
            "event_type",
            "channel",
            "is_read",
            "read_at",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

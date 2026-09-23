from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from apps.tenant.notifications.models import Notification
from apps.tenant.notifications.serializers import NotificationSerializer
from common.permissions.tenant import IsTenantMember
from common.responses.standard import StandardResponseMixin


class NotificationViewSet(StandardResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    List and manage in-app notifications for authenticated users or tenant staff.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["is_read", "event_type", "channel"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(
            Q(recipient_user_id=user.id) | Q(recipient_email=user.email)
        )

    @action(detail=True, methods=["patch"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])

        return self.success_response(
            data=self.get_serializer(notification).data,
            message="Notification marked as read",
        )

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated_count = (
            self.get_queryset()
            .filter(is_read=False)
            .update(
                is_read=True,
                read_at=timezone.now(),
            )
        )
        return self.success_response(
            data={"marked_read": updated_count},
            message=f"{updated_count} notifications marked as read",
        )

from rest_framework import permissions, viewsets
from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(StandardResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Immutable audit trail viewset for compliance, inspection, and security reviews.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]
    filterset_fields = ["action", "resource_type"]
    search_fields = ["actor_email", "resource_type", "action", "resource_id"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        return AuditLog.objects.all()

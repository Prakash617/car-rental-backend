from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets

from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Customer relationship management endpoint for tenant staff and managers.
    Provides customer identity verification, license validation, and rental history.
    """

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_verified", "country"]
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "driver_license_number",
    ]
    ordering_fields = ["created_at", "last_name", "email"]
    ordering = ["-created_at"]

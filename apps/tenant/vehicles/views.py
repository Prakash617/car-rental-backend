from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny

from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Vehicle, VehicleStatus
from .serializers import VehicleDetailSerializer, VehicleSerializer


class VehicleViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Fleet management & public catalog.
    Public requests only see available/reserved vehicles; staff see all.
    """

    queryset = Vehicle.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "transmission", "fuel_type", "branch", "status"]
    search_fields = ["brand", "model", "license_plate"]
    ordering_fields = ["daily_rate", "year", "created_at"]
    ordering = ["brand", "model"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VehicleDetailSerializer
        return VehicleSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        membership = getattr(self.request, "tenant_membership", None)
        if user and user.is_authenticated and membership and membership.is_active:
            return Vehicle.objects.all()
        # Anonymous public catalog only sees non-decommissioned vehicles
        return Vehicle.objects.exclude(status=VehicleStatus.INACTIVE)

    def perform_create(self, serializer):
        vehicle = serializer.save()
        user_email = getattr(self.request.user, "email", "staff@concierge.local")
        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=user_email,
            action="CREATE_VEHICLE",
            resource_type="Vehicle",
            resource_id=str(vehicle.id),
            details={"brand": vehicle.brand, "model": vehicle.model, "plate": vehicle.license_plate},
        )

    def perform_update(self, serializer):
        vehicle = serializer.save()
        user_email = getattr(self.request.user, "email", "staff@concierge.local")
        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=user_email,
            action="UPDATE_VEHICLE",
            resource_type="Vehicle",
            resource_id=str(vehicle.id),
            details={"status": vehicle.status, "plate": vehicle.license_plate},
        )

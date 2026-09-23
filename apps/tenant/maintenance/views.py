from datetime import date

from django.db.models import Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.tenant.bookings.models import Booking
from apps.tenant.maintenance.models import (
    MaintenanceRecord,
    MaintenanceStatus,
    ServiceInterval,
    TelemetryRecord,
    VehicleInspection,
)
from apps.tenant.maintenance.serializers import (
    CompleteMaintenanceSerializer,
    CreateInspectionSerializer,
    MaintenanceRecordSerializer,
    ServiceIntervalSerializer,
    TelemetryRecordSerializer,
    VehicleInspectionSerializer,
)
from apps.tenant.maintenance.services.maintenance_service import MaintenanceService
from apps.tenant.memberships.models import RoleChoices
from apps.tenant.vehicles.models import Vehicle, VehicleStatus
from common.permissions.tenant import HasTenantRole, IsTenantMember
from common.responses.standard import StandardResponseMixin


class MaintenanceViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Fleet maintenance lifecycle management.
    """

    serializer_class = MaintenanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["vehicle", "status", "service_type"]
    search_fields = [
        "vehicle__brand",
        "vehicle__model",
        "vehicle__license_plate",
        "service_type",
        "service_center",
    ]
    ordering_fields = ["scheduled_start", "cost", "created_at"]
    ordering = ["-scheduled_start"]

    def get_queryset(self):
        return MaintenanceRecord.objects.select_related("vehicle")

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[
            permissions.IsAuthenticated,
            HasTenantRole(
                [
                    RoleChoices.OWNER,
                    RoleChoices.ADMIN,
                    RoleChoices.MANAGER,
                    RoleChoices.STAFF,
                ]
            ),
        ],
    )
    def start(self, request, pk=None):
        try:
            record = MaintenanceService.start_maintenance(record_id=pk)
            return self.success_response(
                data=self.get_serializer(record).data,
                message="Maintenance service started. Vehicle set to UNDER MAINTENANCE.",
            )
        except (MaintenanceRecord.DoesNotExist, ValueError) as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[
            permissions.IsAuthenticated,
            HasTenantRole(
                [
                    RoleChoices.OWNER,
                    RoleChoices.ADMIN,
                    RoleChoices.MANAGER,
                    RoleChoices.STAFF,
                ]
            ),
        ],
    )
    def complete(self, request, pk=None):
        serializer = CompleteMaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            record = MaintenanceService.complete_maintenance(
                record_id=pk,
                actual_completion=data.get("actual_completion"),
                odometer_reading=data.get("odometer_reading"),
                cost=data.get("cost"),
                mechanic_notes=data.get("mechanic_notes"),
            )
            return self.success_response(
                data=self.get_serializer(record).data,
                message="Maintenance service completed successfully.",
            )
        except (MaintenanceRecord.DoesNotExist, ValueError) as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)


class VehicleInspectionViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Check-out, check-in, and routine digital inspections.
    """

    serializer_class = VehicleInspectionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["vehicle", "booking", "inspection_type", "has_new_damage"]
    ordering_fields = ["created_at", "odometer"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return VehicleInspection.objects.select_related("vehicle", "booking")

    def create(self, request, *args, **kwargs):
        serializer = CreateInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            vehicle = Vehicle.objects.get(id=data["vehicle_id"])
        except Vehicle.DoesNotExist:
            return self.error_response("Vehicle not found", status_code=status.HTTP_404_NOT_FOUND)

        booking = None
        if data.get("booking_id"):
            try:
                booking = Booking.objects.get(id=data["booking_id"])
            except Booking.DoesNotExist:
                return self.error_response(
                    "Booking not found", status_code=status.HTTP_404_NOT_FOUND
                )

        try:
            inspection = MaintenanceService.perform_inspection(
                vehicle=vehicle,
                inspection_type=data["inspection_type"],
                odometer=data["odometer"],
                fuel_percentage=data["fuel_percentage"],
                booking=booking,
                inspector_id=request.user.id,
                battery_percentage=data.get("battery_percentage"),
                exterior_condition=data.get("exterior_condition"),
                interior_condition=data.get("interior_condition"),
                has_new_damage=data.get("has_new_damage", False),
                damage_description=data.get("damage_description"),
                damage_photos=data.get("damage_photos"),
                customer_signature=data.get("customer_signature"),
            )
            return self.success_response(
                data=VehicleInspectionSerializer(inspection).data,
                message="Inspection recorded successfully",
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)


class TelemetryViewSet(StandardResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Query telemetry and odometer history streams per vehicle.
    """

    serializer_class = TelemetryRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["vehicle", "source"]
    ordering_fields = ["recorded_at", "odometer"]
    ordering = ["-recorded_at"]

    def get_queryset(self):
        return TelemetryRecord.objects.select_related("vehicle")


class ServiceIntervalViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Manage recurring service rules and inspect service due statuses.
    """

    serializer_class = ServiceIntervalSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["vehicle", "is_active"]
    ordering = ["vehicle", "service_name"]

    def get_queryset(self):
        return ServiceInterval.objects.select_related("vehicle")


class FleetHealthOverviewView(StandardResponseMixin, APIView):
    """
    Fleet health summary endpoint for manager dashboards.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, *args, **kwargs):
        total_vehicles = Vehicle.objects.count()
        available_vehicles = Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).count()
        rented_vehicles = Vehicle.objects.filter(status=VehicleStatus.RENTED).count()
        in_maintenance = Vehicle.objects.filter(status=VehicleStatus.MAINTENANCE).count()

        active_services = MaintenanceRecord.objects.filter(
            status__in=[MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]
        ).count()

        # Monthly maintenance expense
        today = date.today()
        month_start = today.replace(day=1)
        monthly_expense = (
            MaintenanceRecord.objects.filter(
                status=MaintenanceStatus.COMPLETED,
                actual_completion__date__gte=month_start,
            ).aggregate(total=Sum("cost"))["total"]
            or 0.00
        )

        return self.success_response(
            data={
                "fleet_size": total_vehicles,
                "available": available_vehicles,
                "rented": rented_vehicles,
                "in_maintenance": in_maintenance,
                "active_maintenance_jobs": active_services,
                "monthly_maintenance_cost": str(monthly_expense),
            },
            message="Fleet health metrics retrieved successfully",
        )

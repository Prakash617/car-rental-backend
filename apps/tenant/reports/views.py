from datetime import date
from decimal import Decimal

from django.db.models import Sum
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers
from rest_framework.views import APIView

from apps.tenant.bookings.models import Booking, BookingStatus, PaymentStatus
from apps.tenant.maintenance.models import MaintenanceRecord, MaintenanceStatus, ServiceInterval
from apps.tenant.payments.models import Payment, PaymentStatusChoices
from apps.tenant.vehicles.models import Vehicle, VehicleStatus
from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin


class DashboardOverviewSerializer(serializers.Serializer):
    fleet_total = serializers.IntegerField()
    fleet_available = serializers.IntegerField()
    fleet_rented = serializers.IntegerField()
    fleet_in_maintenance = serializers.IntegerField()
    fleet_utilization_rate = serializers.FloatField()

    bookings_active = serializers.IntegerField()
    bookings_pending = serializers.IntegerField()
    bookings_completed_this_month = serializers.IntegerField()

    revenue_this_month = serializers.CharField()
    pending_revenue = serializers.CharField()

    maintenance_active_jobs = serializers.IntegerField()
    maintenance_overdue_services = serializers.IntegerField()


class DashboardOverviewView(StandardResponseMixin, APIView):
    """
    Executive dashboard overview providing operational KPIs, fleet utilization,
    revenue metrics, and fleet maintenance alerts.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]

    @extend_schema(responses={200: DashboardOverviewSerializer})
    def get(self, request, *args, **kwargs):
        # Fleet KPIs
        total_fleet = Vehicle.objects.count()
        available_fleet = Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).count()
        rented_fleet = Vehicle.objects.filter(status=VehicleStatus.RENTED).count()
        maintenance_fleet = Vehicle.objects.filter(status=VehicleStatus.MAINTENANCE).count()

        utilization_rate = round((rented_fleet / total_fleet) * 100, 1) if total_fleet > 0 else 0.0

        # Booking KPIs
        active_bookings = Booking.objects.filter(status=BookingStatus.ACTIVE).count()
        pending_bookings = Booking.objects.filter(status=BookingStatus.PENDING).count()

        today = date.today()
        month_start = today.replace(day=1)
        completed_month = Booking.objects.filter(
            status=BookingStatus.COMPLETED,
            return_datetime__date__gte=month_start,
        ).count()

        # Financial Revenue
        revenue_collected = Payment.objects.filter(
            status=PaymentStatusChoices.SUCCEEDED,
            created_at__date__gte=month_start,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        pending_revenue = Booking.objects.filter(
            payment_status=PaymentStatus.UNPAID,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.ACTIVE],
        ).aggregate(total=Sum("total_price"))["total"] or Decimal("0.00")

        # Maintenance alerts
        active_maintenance = MaintenanceRecord.objects.filter(
            status__in=[MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]
        ).count()

        due_services = 0
        for interval in ServiceInterval.objects.select_related("vehicle").filter(is_active=True):
            if interval.is_due():
                due_services += 1

        payload = {
            "fleet_total": total_fleet,
            "fleet_available": available_fleet,
            "fleet_rented": rented_fleet,
            "fleet_in_maintenance": maintenance_fleet,
            "fleet_utilization_rate": utilization_rate,
            "bookings_active": active_bookings,
            "bookings_pending": pending_bookings,
            "bookings_completed_this_month": completed_month,
            "revenue_this_month": str(revenue_collected),
            "pending_revenue": str(pending_revenue),
            "maintenance_active_jobs": active_maintenance,
            "maintenance_overdue_services": due_services,
        }

        return self.success_response(
            data=payload,
            message="Dashboard overview metrics generated successfully",
        )

from datetime import datetime, timedelta

from apps.tenant.bookings.models import Booking, BookingStatus
from apps.tenant.maintenance.models import MaintenanceRecord, MaintenanceStatus
from apps.tenant.vehicles.models import Vehicle, VehicleStatus


class AvailabilityService:
    """
    Dedicated fleet availability engine.
    Detects scheduling overlaps across bookings and maintenance records.
    """

    BUFFER_HOURS = 2  # Cleaning, inspection, and turnaround buffer

    @classmethod
    def is_vehicle_available(
        cls,
        vehicle_id: str,
        pickup_datetime: datetime,
        return_datetime: datetime,
        exclude_booking_id: str | None = None,
    ) -> bool:
        """
        Determines whether the specified vehicle is free for the given date range.
        Considers active bookings, maintenance, and turnaround buffer.
        """
        effective_start = pickup_datetime - timedelta(hours=cls.BUFFER_HOURS)
        effective_end = return_datetime + timedelta(hours=cls.BUFFER_HOURS)

        # 1. Verify vehicle status is not decommissioned or in permanent inactive state
        vehicle = Vehicle.objects.filter(id=vehicle_id).first()
        if not vehicle or vehicle.status in [VehicleStatus.INACTIVE]:
            return False

        # 2. Check conflicting active bookings
        booking_conflicts = Booking.objects.filter(
            vehicle_id=vehicle_id,
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.ACTIVE],
            pickup_datetime__lt=effective_end,
            return_datetime__gt=effective_start,
        )
        if exclude_booking_id:
            booking_conflicts = booking_conflicts.exclude(id=exclude_booking_id)

        if booking_conflicts.exists():
            return False

        # 3. Check conflicting maintenance records
        maintenance_conflicts = MaintenanceRecord.objects.filter(
            vehicle_id=vehicle_id,
            status__in=[MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS],
            scheduled_start__lt=effective_end,
            scheduled_end__gt=effective_start,
        )
        if maintenance_conflicts.exists():
            return False

        return True

    @classmethod
    def get_available_vehicles(
        cls,
        pickup_datetime: datetime,
        return_datetime: datetime,
        branch_id: str | None = None,
        category: str | None = None,
        transmission: str | None = None,
    ):
        """
        Returns a QuerySet of vehicles available for the full duration.
        """
        effective_start = pickup_datetime - timedelta(hours=cls.BUFFER_HOURS)
        effective_end = return_datetime + timedelta(hours=cls.BUFFER_HOURS)

        # Find all vehicle IDs with booking conflicts
        booked_vehicle_ids = Booking.objects.filter(
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.ACTIVE],
            pickup_datetime__lt=effective_end,
            return_datetime__gt=effective_start,
        ).values_list("vehicle_id", flat=True)

        # Find all vehicle IDs with maintenance conflicts
        maintenance_vehicle_ids = MaintenanceRecord.objects.filter(
            status__in=[MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS],
            scheduled_start__lt=effective_end,
            scheduled_end__gt=effective_start,
        ).values_list("vehicle_id", flat=True)

        conflicting_ids = set(booked_vehicle_ids).union(set(maintenance_vehicle_ids))

        # Query eligible vehicles
        queryset = Vehicle.objects.exclude(id__in=conflicting_ids).exclude(
            status=VehicleStatus.INACTIVE
        )

        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if category:
            queryset = queryset.filter(category=category)
        if transmission:
            queryset = queryset.filter(transmission=transmission)

        return queryset

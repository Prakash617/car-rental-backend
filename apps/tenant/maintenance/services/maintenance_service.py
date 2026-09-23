import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.tenant.bookings.models import Booking, BookingStatus
from apps.tenant.bookings.services.availability import AvailabilityService
from apps.tenant.maintenance.models import (
    CleanlinessLevel,
    InspectionType,
    MaintenanceRecord,
    MaintenanceStatus,
    ServiceInterval,
    TelemetryRecord,
    TelemetrySource,
    VehicleInspection,
)
from apps.tenant.vehicles.models import Vehicle, VehicleStatus

logger = logging.getLogger(__name__)


class MaintenanceService:
    """
    Core fleet maintenance lifecycle and digital vehicle inspection service.
    """

    @classmethod
    def schedule_maintenance(
        cls,
        vehicle: Vehicle,
        service_type: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        service_center: str | None = None,
        notes: str | None = None,
    ) -> MaintenanceRecord:
        if scheduled_end <= scheduled_start:
            raise ValueError("scheduled_end must be strictly after scheduled_start")

        # Check vehicle availability (ensure no customer bookings overlap)
        is_available = AvailabilityService.is_vehicle_available(
            vehicle_id=vehicle.id,
            pickup_datetime=scheduled_start,
            return_datetime=scheduled_end,
        )
        if not is_available:
            raise ValueError(
                f"Vehicle {vehicle} is not available during the requested maintenance window."
            )

        with transaction.atomic():
            record = MaintenanceRecord.objects.create(
                vehicle=vehicle,
                service_type=service_type,
                status=MaintenanceStatus.SCHEDULED,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                service_center=service_center,
                notes=notes,
            )

        return record

    @classmethod
    def start_maintenance(cls, record_id: str) -> MaintenanceRecord:
        with transaction.atomic():
            record = MaintenanceRecord.objects.select_for_update().get(id=record_id)
            if record.status not in (MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS):
                raise ValueError(f"Cannot start maintenance with status '{record.status}'")

            record.status = MaintenanceStatus.IN_PROGRESS
            record.save(update_fields=["status", "updated_at"])

            # Transition vehicle to MAINTENANCE
            vehicle = Vehicle.objects.select_for_update().get(id=record.vehicle_id)
            vehicle.status = VehicleStatus.MAINTENANCE
            vehicle.save(update_fields=["status", "updated_at"])

            # Record telemetry
            TelemetryRecord.objects.create(
                vehicle=vehicle,
                odometer=vehicle.mileage,
                source=TelemetrySource.SERVICE,
            )

        return record

    @classmethod
    def complete_maintenance(
        cls,
        record_id: str,
        actual_completion: datetime | None = None,
        odometer_reading: int | None = None,
        cost: Decimal | None = None,
        mechanic_notes: str | None = None,
    ) -> MaintenanceRecord:
        with transaction.atomic():
            record = MaintenanceRecord.objects.select_for_update().get(id=record_id)
            if record.status == MaintenanceStatus.COMPLETED:
                return record

            record.status = MaintenanceStatus.COMPLETED
            record.actual_completion = actual_completion or timezone.now()

            if cost is not None:
                record.cost = cost
            if mechanic_notes:
                record.notes = (record.notes or "") + f"\nMechanic: {mechanic_notes}"

            vehicle = Vehicle.objects.select_for_update().get(id=record.vehicle_id)

            if odometer_reading is not None:
                if odometer_reading < vehicle.mileage:
                    raise ValueError(
                        f"Odometer reading {odometer_reading} cannot be lower than current mileage {vehicle.mileage}"
                    )
                record.odometer_reading = odometer_reading
                vehicle.mileage = odometer_reading

                # Update matching ServiceIntervals
                ServiceInterval.objects.filter(
                    vehicle=vehicle,
                    service_name__iexact=record.service_type,
                ).update(
                    last_service_mileage=odometer_reading,
                    last_service_date=date.today(),
                )

                # Record telemetry
                TelemetryRecord.objects.create(
                    vehicle=vehicle,
                    odometer=odometer_reading,
                    source=TelemetrySource.SERVICE,
                )

            record.save(
                update_fields=[
                    "status",
                    "actual_completion",
                    "cost",
                    "notes",
                    "odometer_reading",
                    "updated_at",
                ]
            )

            # Restore vehicle to AVAILABLE if not currently rented
            active_booking_exists = Booking.objects.filter(
                vehicle=vehicle,
                status=BookingStatus.ACTIVE,
            ).exists()

            if not active_booking_exists:
                vehicle.status = VehicleStatus.AVAILABLE

            vehicle.save(update_fields=["mileage", "status", "updated_at"])

        return record

    @classmethod
    def perform_inspection(
        cls,
        vehicle: Vehicle,
        inspection_type: str,
        odometer: int,
        fuel_percentage: int,
        booking: Booking | None = None,
        inspector_id: Any = None,
        battery_percentage: int | None = None,
        exterior_condition: str = CleanlinessLevel.GOOD,
        interior_condition: str = CleanlinessLevel.GOOD,
        has_new_damage: bool = False,
        damage_description: str | None = None,
        damage_photos: list[str] | None = None,
        customer_signature: str | None = None,
    ) -> VehicleInspection:
        """
        Executes a pre-rental or post-rental inspection, recording odometer/fuel state
        and synchronizing booking and vehicle statuses.
        """
        with transaction.atomic():
            vehicle_locked = Vehicle.objects.select_for_update().get(id=vehicle.id)

            if odometer < vehicle_locked.mileage:
                raise ValueError(
                    f"Inspection odometer {odometer} cannot be less than vehicle recorded mileage {vehicle_locked.mileage}"
                )

            # 1. Create Inspection Record
            inspection = VehicleInspection.objects.create(
                vehicle=vehicle_locked,
                booking=booking,
                inspector_id=inspector_id,
                inspection_type=inspection_type,
                odometer=odometer,
                fuel_percentage=fuel_percentage,
                battery_percentage=battery_percentage,
                exterior_condition=exterior_condition,
                interior_condition=interior_condition,
                has_new_damage=has_new_damage,
                damage_description=damage_description,
                damage_photos=damage_photos or [],
                customer_signature=customer_signature,
            )

            # 2. Update Vehicle Current Mileage
            vehicle_locked.mileage = odometer

            # 3. Create Telemetry Stream Entry
            source_map = {
                InspectionType.CHECK_OUT: TelemetrySource.TRIP_CHECKOUT,
                InspectionType.CHECK_IN: TelemetrySource.TRIP_CHECKIN,
                InspectionType.ROUTINE: TelemetrySource.MANUAL_INSPECTION,
            }
            TelemetryRecord.objects.create(
                vehicle=vehicle_locked,
                odometer=odometer,
                fuel_level=fuel_percentage,
                source=source_map.get(inspection_type, TelemetrySource.MANUAL_INSPECTION),
            )

            # 4. Booking & Vehicle Status Handshake
            if inspection_type == InspectionType.CHECK_OUT:
                vehicle_locked.status = VehicleStatus.RENTED
                if booking:
                    booking_locked = Booking.objects.select_for_update().get(id=booking.id)
                    booking_locked.status = BookingStatus.ACTIVE
                    booking_locked.save(update_fields=["status", "updated_at"])

            elif inspection_type == InspectionType.CHECK_IN:
                if has_new_damage:
                    # Vehicle has damage, route to maintenance or review
                    vehicle_locked.status = VehicleStatus.MAINTENANCE
                else:
                    vehicle_locked.status = VehicleStatus.AVAILABLE

                if booking:
                    booking_locked = Booking.objects.select_for_update().get(id=booking.id)
                    booking_locked.status = BookingStatus.COMPLETED
                    if has_new_damage:
                        booking_locked.notes = (
                            booking_locked.notes or ""
                        ) + f"\n[DAMAGE DETECTED AT RETURN]: {damage_description}"
                    booking_locked.save(update_fields=["status", "notes", "updated_at"])

            vehicle_locked.save(update_fields=["mileage", "status", "updated_at"])

        return inspection

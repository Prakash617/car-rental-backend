import uuid
from datetime import date

from django.db import models

from apps.tenant.vehicles.models import Vehicle


class MaintenanceStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class InspectionType(models.TextChoices):
    CHECK_OUT = "check_out", "Check-Out (Pre-Rental)"
    CHECK_IN = "check_in", "Check-In (Post-Rental)"
    ROUTINE = "routine", "Routine Maintenance Inspection"


class CleanlinessLevel(models.TextChoices):
    EXCELLENT = "excellent", "Spotless / Pristine"
    GOOD = "good", "Clean"
    MODERATE = "moderate", "Lightly Soiled"
    POOR = "poor", "Requires Deep Detailing"


class MaintenanceRecord(models.Model):
    """
    Fleet maintenance and repair log.
    Overlapping maintenance records actively block vehicle booking availability.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="maintenance_records"
    )

    service_type = models.CharField(
        "Service Type", max_length=100
    )  # e.g. "Oil & Filter Change", "Brake Pad Replacement", "Tire Rotation"
    status = models.CharField(
        max_length=20, choices=MaintenanceStatus.choices, default=MaintenanceStatus.SCHEDULED
    )

    scheduled_start = models.DateTimeField("Scheduled Start Time")
    scheduled_end = models.DateTimeField("Scheduled Completion Time")
    actual_completion = models.DateTimeField("Actual Completion Time", null=True, blank=True)

    odometer_reading = models.PositiveIntegerField("Odometer at Service", null=True, blank=True)
    cost = models.DecimalField("Service Cost", max_digits=10, decimal_places=2, default=0.00)
    service_center = models.CharField(
        "Service Center / Provider", max_length=120, blank=True, null=True
    )
    notes = models.TextField("Mechanic Notes", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Maintenance Record"
        verbose_name_plural = "Maintenance Records"
        ordering = ["-scheduled_start"]
        indexes = [
            models.Index(fields=["vehicle", "status"], name="idx_maint_veh_status"),
            models.Index(fields=["scheduled_start", "scheduled_end"], name="idx_maint_dates"),
        ]

    def __str__(self):
        return f"{self.vehicle} - {self.service_type} ({self.status})"


class VehicleInspection(models.Model):
    """
    Digital vehicle inspection log recording fuel, odometer, cleanliness, and condition
    during customer check-out, return check-in, or maintenance audits.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="inspections")
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    inspector_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Logical PlatformUser ID who conducted the inspection",
    )
    inspection_type = models.CharField(
        max_length=20,
        choices=InspectionType.choices,
        default=InspectionType.CHECK_OUT,
    )
    odometer = models.PositiveIntegerField("Odometer Reading")
    fuel_percentage = models.PositiveSmallIntegerField("Fuel Level (0-100%)", default=100)
    battery_percentage = models.PositiveSmallIntegerField(
        "EV Battery Charge (0-100%)", null=True, blank=True
    )
    exterior_condition = models.CharField(
        max_length=20,
        choices=CleanlinessLevel.choices,
        default=CleanlinessLevel.GOOD,
    )
    interior_condition = models.CharField(
        max_length=20,
        choices=CleanlinessLevel.choices,
        default=CleanlinessLevel.GOOD,
    )
    has_new_damage = models.BooleanField(default=False)
    damage_description = models.TextField(blank=True, null=True)
    damage_photos = models.JSONField(
        default=list,
        blank=True,
        help_text="List of photo URLs/keys documenting damage evidence",
    )
    customer_signature = models.TextField(
        blank=True,
        null=True,
        help_text="Customer digital sign-off token or SVG representation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "inspection_type"]),
            models.Index(fields=["booking", "inspection_type"]),
        ]

    def __str__(self):
        return f"Inspection ({self.inspection_type}) for {self.vehicle} [{self.created_at.strftime('%Y-%m-%d')}]"


class TelemetrySource(models.TextChoices):
    MANUAL_INSPECTION = "manual_inspection", "Manual Inspection"
    TRIP_CHECKOUT = "trip_checkout", "Trip Check-Out"
    TRIP_CHECKIN = "trip_checkin", "Trip Check-In"
    SERVICE = "service", "Service / Maintenance"
    GPS_TRACKER = "gps_tracker", "GPS Telemetry Unit"


class TelemetryRecord(models.Model):
    """
    Chronological odometer and location telemetry stream for fleet auditing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="telemetry_records")
    odometer = models.PositiveIntegerField("Odometer Reading")
    fuel_level = models.PositiveSmallIntegerField("Fuel Percentage", null=True, blank=True)
    source = models.CharField(
        max_length=30,
        choices=TelemetrySource.choices,
        default=TelemetrySource.MANUAL_INSPECTION,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    speed_kph = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["vehicle", "-recorded_at"]),
        ]

    def __str__(self):
        return f"Telemetry {self.vehicle} @ {self.odometer}km ({self.source})"


class ServiceInterval(models.Model):
    """
    Configurable recurring service schedule per vehicle (e.g. oil change every 10,000 km
    or tire rotation every 180 days).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="service_intervals")
    service_name = models.CharField(max_length=100)
    interval_mileage = models.PositiveIntegerField(
        "Interval in Distance (km/mi)", null=True, blank=True
    )
    interval_days = models.PositiveIntegerField("Interval in Days", null=True, blank=True)
    last_service_mileage = models.PositiveIntegerField(default=0)
    last_service_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vehicle", "service_name"]

    def is_due(self, current_mileage: int, current_date: date | None = None) -> bool:
        check_date = current_date or date.today()
        # Mileage check
        if (
            self.interval_mileage
            and (current_mileage - self.last_service_mileage) >= self.interval_mileage
        ):
            return True
        # Time interval check
        if self.interval_days and self.last_service_date:
            days_elapsed = (check_date - self.last_service_date).days
            if days_elapsed >= self.interval_days:
                return True
        return False

    def due_status(self, current_mileage: int, current_date: date | None = None) -> str:
        if self.is_due(current_mileage, current_date):
            return "overdue"
        check_date = current_date or date.today()
        # Near warning (90% of interval)
        if self.interval_mileage:
            delta = current_mileage - self.last_service_mileage
            if delta >= (self.interval_mileage * 0.9):
                return "due_soon"
        if self.interval_days and self.last_service_date:
            days_elapsed = (check_date - self.last_service_date).days
            if days_elapsed >= (self.interval_days * 0.9):
                return "due_soon"
        return "ok"

    def __str__(self):
        return f"{self.vehicle} — {self.service_name} (every {self.interval_mileage or 'N/A'}km / {self.interval_days or 'N/A'}d)"

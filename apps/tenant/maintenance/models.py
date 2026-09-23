import uuid

from django.db import models

from apps.tenant.vehicles.models import Vehicle


class MaintenanceStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class MaintenanceRecord(models.Model):
    """
    Fleet maintenance and inspection log. Overlapping scheduled maintenance
    actively blocks vehicle booking availability.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="maintenance_records"
    )

    service_type = models.CharField(
        "Service Type", max_length=100
    )  # e.g. "Oil Change", "Brake Pad Replacement"
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

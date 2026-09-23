import uuid

from django.db import models

from apps.tenant.branches.models import Branch


class VehicleCategory(models.TextChoices):
    ECONOMY = "economy", "Economy"
    COMPACT = "compact", "Compact"
    SEDAN = "sedan", "Sedan"
    SUV = "suv", "SUV"
    LUXURY = "luxury", "Luxury"
    SPORTS = "sports", "Sports"
    VAN = "van", "Van / Minivan"
    ELECTRIC = "electric", "Electric"


class TransmissionType(models.TextChoices):
    AUTOMATIC = "automatic", "Automatic"
    MANUAL = "manual", "Manual"


class FuelType(models.TextChoices):
    PETROL = "petrol", "Petrol / Gasoline"
    DIESEL = "diesel", "Diesel"
    HYBRID = "hybrid", "Hybrid"
    ELECTRIC = "electric", "All-Electric"


class VehicleStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    RENTED = "rented", "Rented"
    MAINTENANCE = "maintenance", "Under Maintenance"
    INACTIVE = "inactive", "Inactive / Decommissioned"


class Vehicle(models.Model):
    """
    Fleet asset representation within the tenant schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT, related_name="vehicles")

    brand = models.CharField("Brand / Make", max_length=60)
    model = models.CharField("Model", max_length=60)
    year = models.PositiveIntegerField("Year")
    license_plate = models.CharField("License Plate", max_length=20, unique=True)
    vin = models.CharField(
        "Vehicle Identification Number (VIN)", max_length=17, unique=True, null=True, blank=True
    )

    category = models.CharField(
        max_length=30, choices=VehicleCategory.choices, default=VehicleCategory.SEDAN
    )
    transmission = models.CharField(
        max_length=20, choices=TransmissionType.choices, default=TransmissionType.AUTOMATIC
    )
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, default=FuelType.PETROL)

    seats = models.PositiveSmallIntegerField("Seats", default=5)
    doors = models.PositiveSmallIntegerField("Doors", default=4)
    mileage = models.PositiveIntegerField("Current Odometer (km/mi)", default=0)
    color = models.CharField("Exterior Color", max_length=30)

    status = models.CharField(
        max_length=20, choices=VehicleStatus.choices, default=VehicleStatus.AVAILABLE
    )

    # Pricing Tiers
    daily_rate = models.DecimalField("Daily Base Rate", max_digits=10, decimal_places=2)
    weekly_rate = models.DecimalField(
        "Weekly Discounted Daily Rate", max_digits=10, decimal_places=2, null=True, blank=True
    )
    monthly_rate = models.DecimalField(
        "Monthly Discounted Daily Rate", max_digits=10, decimal_places=2, null=True, blank=True
    )
    deposit_amount = models.DecimalField(
        "Security Deposit Required", max_digits=10, decimal_places=2, default=0.00
    )

    # Rich specs & media
    features = models.JSONField("Features & Amenities", default=list, blank=True)
    images = models.JSONField("Image URLs & Keys", default=list, blank=True)
    description = models.TextField("Public Marketing Description", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"
        ordering = ["brand", "model", "-year"]
        indexes = [
            models.Index(fields=["status"], name="idx_vehicle_status"),
            models.Index(fields=["category"], name="idx_vehicle_category"),
            models.Index(fields=["branch"], name="idx_vehicle_branch"),
            models.Index(fields=["license_plate"], name="idx_vehicle_plate"),
        ]

    def __str__(self):
        return f"{self.year} {self.brand} {self.model} ({self.license_plate})"

    @property
    def display_name(self):
        return f"{self.brand} {self.model}"

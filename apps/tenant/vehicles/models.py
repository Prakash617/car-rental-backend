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


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Category Name", max_length=60)
    slug = models.SlugField("Slug", max_length=60, unique=True)
    description = models.TextField("Description", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Transmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Transmission Name", max_length=60)
    slug = models.SlugField("Slug", max_length=60, unique=True)
    description = models.TextField("Description", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transmission"
        verbose_name_plural = "Transmissions"
        ordering = ["name"]

    def __str__(self):
        return self.name


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
        max_length=60, default="sedan"
    )
    transmission = models.CharField(
        max_length=60, default="automatic"
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
    rate_4h = models.DecimalField("4-Hour Rate", max_digits=10, decimal_places=2, null=True, blank=True)
    rate_8h = models.DecimalField("8-Hour Rate", max_digits=10, decimal_places=2, null=True, blank=True)
    fuel_rate_per_km = models.DecimalField("Fuel Rate per KM", max_digits=6, decimal_places=2, default=2.50)
    weekly_rate = models.DecimalField(
        "Weekly Discounted Daily Rate", max_digits=10, decimal_places=2, null=True, blank=True
    )
    monthly_rate = models.DecimalField(
        "Monthly Discounted Daily Rate", max_digits=10, decimal_places=2, null=True, blank=True
    )
    deposit_amount = models.DecimalField(
        "Security Deposit Required", max_digits=10, decimal_places=2, default=0.00
    )

    # Verification and Driver details (matching Sajilo Rental marketplace)
    is_verified = models.BooleanField("Verified Vehicle", default=True)
    driver_included = models.BooleanField("Driver Included", default=True)
    driver_name = models.CharField("Driver Name", max_length=100, default="Rohan Kharel", blank=True)
    driver_experience = models.CharField("Driver Experience", max_length=50, default="5+ Years", blank=True)

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

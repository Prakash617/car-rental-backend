import uuid

from django.db import models


class SeasonalRate(models.Model):
    """
    Seasonal price multipliers applied to base rates for specified date ranges.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Season Name", max_length=100)  # e.g. "Summer Peak Demand"
    start_date = models.DateField("Start Date")
    end_date = models.DateField("End Date")
    multiplier = models.DecimalField(
        "Rate Multiplier",
        max_digits=4,
        decimal_places=2,
        default=1.00,
        help_text="e.g. 1.25 for +25% surge, 0.90 for -10% off-season discount",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Seasonal Rate"
        verbose_name_plural = "Seasonal Rates"
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.name} (x{self.multiplier})"


class DiscountType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage Off (%)"
    FIXED = "fixed", "Fixed Amount Off"


class Coupon(models.Model):
    """
    Promotional voucher codes applied at checkout.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Promo Code", max_length=30, unique=True)
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField("Discount Value", max_digits=10, decimal_places=2)

    min_rental_days = models.PositiveSmallIntegerField("Minimum Rental Days", default=1)
    max_uses = models.PositiveIntegerField("Max Uses Allowed", null=True, blank=True)
    times_used = models.PositiveIntegerField("Times Used", default=0)

    valid_from = models.DateTimeField("Valid From", null=True, blank=True)
    valid_to = models.DateTimeField("Valid To", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} ({self.discount_value} {self.discount_type})"


class AddonPricingType(models.TextChoices):
    PER_DAY = "per_day", "Per Day"
    PER_RENTAL = "per_rental", "Per Rental Flat Fee"


class ExtraAddon(models.Model):
    """
    Optional add-ons available during booking checkout (GPS, Child Seat, Full Insurance).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Add-on Name", max_length=100)
    description = models.TextField("Description", blank=True, null=True)
    price = models.DecimalField("Price", max_digits=10, decimal_places=2)
    pricing_type = models.CharField(
        max_length=20, choices=AddonPricingType.choices, default=AddonPricingType.PER_DAY
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Extra Add-on"
        verbose_name_plural = "Extra Add-ons"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (${self.price}/{self.pricing_type})"

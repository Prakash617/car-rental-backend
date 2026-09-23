import uuid

from django.db import models


class Branch(models.Model):
    """
    Physical branch or depot location for vehicle collection and return.
    Stored inside each tenant schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Branch Name", max_length=100)
    code = models.CharField("Branch Code", max_length=10)

    address_line1 = models.CharField("Address Line 1", max_length=255)
    address_line2 = models.CharField("Address Line 2", max_length=255, blank=True, null=True)
    city = models.CharField("City", max_length=100)
    state = models.CharField("State / Province", max_length=100, blank=True, null=True)
    postal_code = models.CharField("Postal / ZIP Code", max_length=20)
    country = models.CharField("Country Code", max_length=2, default="US")

    latitude = models.DecimalField(
        "Latitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "Longitude", max_digits=9, decimal_places=6, null=True, blank=True
    )

    phone = models.CharField("Phone", max_length=30)
    email = models.EmailField("Email", max_length=255)

    is_active = models.BooleanField("Is Active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["city"], name="idx_branch_city"),
            models.Index(fields=["code"], name="idx_branch_code"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

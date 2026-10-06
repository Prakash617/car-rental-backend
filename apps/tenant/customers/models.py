import uuid

from django.db import models


class Customer(models.Model):
    """
    Renter / client profile associated with a specific tenant schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField("First Name", max_length=60)
    last_name = models.CharField("Last Name", max_length=60)
    email = models.EmailField("Email Address", max_length=255)
    phone = models.CharField("Phone Number", max_length=30)

    driver_license_number = models.CharField("Driver's License Number", max_length=50, blank=True, default="CHAUFFEUR-BOOKING")
    license_expiry_date = models.DateField("License Expiry Date", null=True, blank=True)
    date_of_birth = models.DateField("Date of Birth", null=True, blank=True)
    country = models.CharField("Country Code", max_length=2, default="NP")

    is_verified = models.BooleanField("Identity Verified", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"], name="idx_customer_email"),
            models.Index(fields=["driver_license_number"], name="idx_customer_license"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

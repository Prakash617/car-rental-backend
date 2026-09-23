import uuid

from django.db import models


class PaymentProviderChoices(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    ESEWA = "esewa", "eSewa"
    KHALTI = "khalti", "Khalti"
    PAYPAL = "paypal", "PayPal"
    CASH = "cash", "Cash"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"


class PaymentStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"
    REQUIRES_ACTION = "requires_action", "Requires Customer Action"


class PaymentTypeChoices(models.TextChoices):
    RENTAL_CHARGE = "rental_charge", "Rental Charge"
    SECURITY_DEPOSIT = "security_deposit", "Security Deposit Pre-Auth"
    DEPOSIT_REFUND = "deposit_refund", "Deposit Refund"
    DAMAGE_CHARGE = "damage_charge", "Damage / Extra Charge"


class Payment(models.Model):
    """
    Immutable ledger of payment transactions for rental bookings within a tenant schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="payments",
        db_index=True,
    )
    provider = models.CharField(
        max_length=30,
        choices=PaymentProviderChoices.choices,
        default=PaymentProviderChoices.STRIPE,
        db_index=True,
    )
    payment_type = models.CharField(
        max_length=30,
        choices=PaymentTypeChoices.choices,
        default=PaymentTypeChoices.RENTAL_CHARGE,
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    transaction_reference = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Provider gateway transaction or payment intent reference (e.g., pi_xxx, ch_xxx)",
    )
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique client-supplied or system-generated idempotency token",
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw or structured gateway response payload",
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["provider", "status"]),
        ]

    def __str__(self):
        return (
            f"Payment {self.id} ({self.provider} - {self.amount} {self.currency}) [{self.status}]"
        )


class WebhookStatusChoices(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    IGNORED = "ignored", "Ignored"


class WebhookEvent(models.Model):
    """
    Idempotency ledger for incoming gateway webhook events to defend against replay attacks.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(
        max_length=30,
        choices=PaymentProviderChoices.choices,
        db_index=True,
    )
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Gateway event ID (e.g. evt_xxx for Stripe)",
    )
    event_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=WebhookStatusChoices.choices,
        default=WebhookStatusChoices.RECEIVED,
        db_index=True,
    )
    payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="unique_provider_event_id",
            )
        ]
        indexes = [
            models.Index(fields=["provider", "status"]),
        ]

    def __str__(self):
        return f"WebhookEvent {self.provider}:{self.event_id} ({self.event_type}) [{self.status}]"


class SecurityDepositStatusChoices(models.TextChoices):
    AUTHORIZED = "authorized", "Authorized"
    CAPTURED = "captured", "Captured"
    RELEASED = "released", "Released"
    PARTIALLY_CAPTURED = "partially_captured", "Partially Captured"


class SecurityDeposit(models.Model):
    """
    Tracks pre-authorized security deposits held for rental bookings.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="security_deposit_hold",
    )
    hold_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Pre-auth authorization transaction or intent ID",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=30,
        choices=SecurityDepositStatusChoices.choices,
        default=SecurityDepositStatusChoices.AUTHORIZED,
        db_index=True,
    )
    captured_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    released_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reason = models.TextField(blank=True, help_text="Reason for capture or release notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SecurityDeposit {self.id} for Booking {self.booking.booking_reference} [{self.status}]"

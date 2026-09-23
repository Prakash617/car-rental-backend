import uuid

from django.db import models


class NotificationChannelChoices(models.TextChoices):
    IN_APP = "in_app", "In-App"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class NotificationEventTypeChoices(models.TextChoices):
    BOOKING_CONFIRMATION = "booking_confirmation", "Booking Confirmation"
    BOOKING_CANCELLATION = "booking_cancellation", "Booking Cancellation"
    PAYMENT_RECEIPT = "payment_receipt", "Payment Receipt"
    PAYMENT_FAILURE = "payment_failure", "Payment Failure"
    PICKUP_REMINDER = "pickup_reminder", "Pickup Reminder"
    RETURN_REMINDER = "return_reminder", "Return Reminder"
    OVERDUE_NOTICE = "overdue_notice", "Overdue Notice"
    SECURITY_DEPOSIT_UPDATE = "security_deposit_update", "Security Deposit Update"
    TEAM_INVITATION = "team_invitation", "Team Invitation"


class Notification(models.Model):
    """
    In-app notifications stored inside the tenant schema for staff and renters.
    Uses logical recipient_user_id to maintain clean PostgreSQL schema separation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_email = models.EmailField(db_index=True)
    recipient_user_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Logical UUID reference to PlatformUser in public schema",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    event_type = models.CharField(
        max_length=50,
        choices=NotificationEventTypeChoices.choices,
        db_index=True,
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannelChoices.choices,
        default=NotificationChannelChoices.IN_APP,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contextual details (e.g. booking_id, vehicle_name, payment_id)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_email", "is_read"]),
            models.Index(fields=["recipient_user_id", "is_read"]),
        ]

    def __str__(self):
        return f"Notification {self.id} for {self.recipient_email} [{self.event_type}]"

    @property
    def recipient_user(self):
        if not self.recipient_user_id:
            return None
        from apps.platform.platform_users.models import PlatformUser

        return PlatformUser.objects.filter(id=self.recipient_user_id).first()


class NotificationLog(models.Model):
    """
    De-duplication ledger to ensure email and SMS notifications are never sent twice
    for the exact same business trigger (e.g. background retry protection).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Idempotency key for event, e.g. 'booking_confirmation:BK-837192'",
    )
    recipient = models.EmailField(db_index=True)
    channel = models.CharField(max_length=20, choices=NotificationChannelChoices.choices)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event_key", "recipient", "channel"],
                name="unique_notification_event_log",
            )
        ]

    def __str__(self):
        return f"NotificationLog {self.event_key} -> {self.recipient} via {self.channel}"

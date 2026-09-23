import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from apps.tenant.notifications.models import (
    NotificationChannelChoices,
    NotificationLog,
)
from integrations.email.service import EmailService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email_async(
    self,
    schema_name: str,
    recipient_email: str,
    subject: str,
    template_name: str,
    context: dict[str, Any],
    event_key: str | None = None,
):
    """
    Celery worker task to asynchronously send an email within the given tenant schema
    while enforcing idempotency via NotificationLog.
    """
    try:
        with schema_context(schema_name):
            if event_key:
                already_sent = NotificationLog.objects.filter(
                    event_key=event_key,
                    recipient=recipient_email,
                    channel=NotificationChannelChoices.EMAIL,
                ).exists()
                if already_sent:
                    logger.info(
                        f"Notification '{event_key}' already sent to {recipient_email}. Skipping duplicate."
                    )
                    return True

            success = EmailService.send_template_email(
                to_email=recipient_email,
                subject=subject,
                template_name=template_name,
                context=context,
            )

            if success and event_key:
                NotificationLog.objects.create(
                    event_key=event_key,
                    recipient=recipient_email,
                    channel=NotificationChannelChoices.EMAIL,
                )

            return success
    except Exception as exc:
        logger.error(
            f"Failed to dispatch async notification email to {recipient_email} in schema {schema_name}: {exc}"
        )
        raise self.retry(exc=exc) from exc


@shared_task
def send_pickup_reminders_all_tenants():
    """
    Periodic Celery Beat task scanning upcoming pickups in the next 24 hours
    across all active tenant schemas.
    """
    TenantModel = get_tenant_model()
    tenants = TenantModel.objects.filter(is_active=True).exclude(schema_name="public")

    now = timezone.now()
    cutoff = now + timedelta(hours=24)

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                from apps.tenant.bookings.models import Booking, BookingStatus

                upcoming_bookings = Booking.objects.filter(
                    status=BookingStatus.CONFIRMED,
                    pickup_datetime__gte=now,
                    pickup_datetime__lte=cutoff,
                ).select_related("customer", "pickup_branch", "vehicle")

                for booking in upcoming_bookings:
                    event_key = f"pickup_reminder:{booking.booking_reference}"
                    if not booking.customer or not booking.customer.email:
                        continue

                    # Check if reminder already logged
                    if NotificationLog.objects.filter(
                        event_key=event_key,
                        recipient=booking.customer.email,
                        channel=NotificationChannelChoices.EMAIL,
                    ).exists():
                        continue

                    # Dispatch reminder
                    send_notification_email_async.delay(
                        schema_name=tenant.schema_name,
                        recipient_email=booking.customer.email,
                        subject=f"Pickup Reminder — Booking #{booking.booking_reference}",
                        template_name="emails/pickup_reminder.html",
                        context={
                            "customer_name": f"{booking.customer.first_name} {booking.customer.last_name}",
                            "booking_reference": booking.booking_reference,
                            "vehicle_name": f"{booking.vehicle.brand} {booking.vehicle.model}",
                            "pickup_branch_address": booking.pickup_branch.address_line1
                            if booking.pickup_branch
                            else "Main Branch",
                            "pickup_datetime": booking.pickup_datetime.strftime(
                                "%Y-%m-%d %H:%M UTC"
                            ),
                        },
                        event_key=event_key,
                    )
                    logger.info(
                        f"Enqueued pickup reminder for booking #{booking.booking_reference} ({tenant.schema_name})"
                    )
        except Exception as e:
            logger.error(f"Error checking pickup reminders for tenant {tenant.schema_name}: {e}")

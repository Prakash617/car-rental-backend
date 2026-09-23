import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import connection

from apps.tenant.notifications.models import (
    Notification,
    NotificationChannelChoices,
    NotificationEventTypeChoices,
)
from apps.tenant.notifications.tasks import send_notification_email_async
from integrations.email.service import EmailService

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Orchestration service for in-app and out-of-band email notifications
    within the active tenant schema.
    """

    @classmethod
    def dispatch_in_app(
        cls,
        recipient_email: str,
        title: str,
        message: str,
        event_type: str,
        recipient_user: Any = None,
        recipient_user_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        uid = recipient_user_id or (getattr(recipient_user, "id", None) if recipient_user else None)
        return Notification.objects.create(
            recipient_email=recipient_email,
            recipient_user_id=uid,
            title=title,
            message=message,
            event_type=event_type,
            channel=NotificationChannelChoices.IN_APP,
            metadata=metadata or {},
        )

    @classmethod
    def dispatch_booking_confirmation(cls, booking: Any) -> tuple[Notification | None, bool]:
        customer = getattr(booking, "customer", None)
        email = customer.email if customer else None
        if not email:
            logger.warning(f"Booking {booking.booking_reference} has no customer email")
            return None, False

        vehicle = getattr(booking, "vehicle", None)
        vehicle_name = f"{vehicle.brand} {vehicle.model}" if vehicle else "Vehicle"

        # 1. In-App Notification
        in_app_notif = cls.dispatch_in_app(
            recipient_email=email,
            title=f"Booking Confirmed — #{booking.booking_reference}",
            message=f"Your reservation for {vehicle_name} has been confirmed.",
            event_type=NotificationEventTypeChoices.BOOKING_CONFIRMATION,
            metadata={
                "booking_id": str(booking.id),
                "booking_reference": booking.booking_reference,
            },
        )

        # 2. Email Delivery (Async via Celery or sync in test/debug)
        event_key = f"booking_confirmation:{booking.booking_reference}"
        schema_name = connection.schema_name

        pickup_branch = getattr(booking, "pickup_branch", None)
        return_branch = getattr(booking, "return_branch", None)

        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "booking_reference": booking.booking_reference,
            "vehicle_name": vehicle_name,
            "pickup_branch": pickup_branch.name if pickup_branch else "Main Branch",
            "pickup_datetime": booking.pickup_datetime.strftime("%Y-%m-%d %H:%M UTC"),
            "return_branch": return_branch.name if return_branch else "Main Branch",
            "return_datetime": booking.return_datetime.strftime("%Y-%m-%d %H:%M UTC"),
            "total_amount": f"{booking.total_price:.2f}",
            "currency": getattr(booking, "currency", "USD"),
            "security_deposit": f"{booking.deposit_amount:.2f}"
            if getattr(booking, "deposit_amount", None)
            else None,
        }

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) or getattr(
            settings, "TESTING", False
        ):
            # Synchronous in tests
            EmailService.send_booking_confirmation(booking, recipient_email=email)
        else:
            send_notification_email_async.delay(
                schema_name=schema_name,
                recipient_email=email,
                subject=f"Booking Confirmed — #{booking.booking_reference}",
                template_name="emails/booking_confirmation.html",
                context=context,
                event_key=event_key,
            )

        return in_app_notif, True

    @classmethod
    def dispatch_payment_receipt(cls, payment: Any) -> tuple[Notification | None, bool]:
        booking = getattr(payment, "booking", None)
        customer = getattr(booking, "customer", None) if booking else None
        email = customer.email if customer else None
        if not email:
            logger.warning(f"Payment {payment.id} has no customer email")
            return None, False

        # 1. In-App Notification
        in_app_notif = cls.dispatch_in_app(
            recipient_email=email,
            title=f"Payment Received — {payment.currency} {payment.amount:.2f}",
            message=f"Payment of {payment.currency} {payment.amount:.2f} via {payment.provider} was successful.",
            event_type=NotificationEventTypeChoices.PAYMENT_RECEIPT,
            metadata={"payment_id": str(payment.id), "amount": str(payment.amount)},
        )

        # 2. Email Delivery
        event_key = f"payment_receipt:{payment.id}"
        schema_name = connection.schema_name

        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "payment_id": str(payment.id)[:8].upper(),
            "booking_reference": booking.booking_reference if booking else "N/A",
            "provider": payment.provider,
            "transaction_reference": payment.transaction_reference or "N/A",
            "payment_date": payment.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "status": payment.status,
        }

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) or getattr(
            settings, "TESTING", False
        ):
            EmailService.send_payment_receipt(payment, recipient_email=email)
        else:
            send_notification_email_async.delay(
                schema_name=schema_name,
                recipient_email=email,
                subject=f"Payment Receipt — #{booking.booking_reference if booking else payment.id}",
                template_name="emails/payment_receipt.html",
                context=context,
                event_key=event_key,
            )

        return in_app_notif, True

    @classmethod
    def dispatch_booking_cancellation(
        cls,
        booking: Any,
        refund_amount: Decimal | None = None,
        reason: str | None = None,
    ) -> tuple[Notification | None, bool]:
        customer = getattr(booking, "customer", None)
        email = customer.email if customer else None
        if not email:
            return None, False

        in_app_notif = cls.dispatch_in_app(
            recipient_email=email,
            title=f"Booking Cancelled — #{booking.booking_reference}",
            message=f"Reservation #{booking.booking_reference} has been cancelled. Reason: {reason or 'N/A'}",
            event_type=NotificationEventTypeChoices.BOOKING_CANCELLATION,
            metadata={
                "booking_id": str(booking.id),
                "refund_amount": str(refund_amount) if refund_amount else None,
            },
        )

        event_key = f"booking_cancellation:{booking.booking_reference}"
        schema_name = connection.schema_name

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) or getattr(
            settings, "TESTING", False
        ):
            EmailService.send_booking_cancellation(
                booking, recipient_email=email, refund_amount=refund_amount, reason=reason
            )
        else:
            vehicle = getattr(booking, "vehicle", None)
            context = {
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "booking_reference": booking.booking_reference,
                "vehicle_name": f"{vehicle.brand} {vehicle.model}" if vehicle else "Vehicle",
                "cancellation_reason": reason or getattr(booking, "notes", ""),
                "refund_amount": f"{refund_amount:.2f}" if refund_amount else None,
                "currency": getattr(booking, "currency", "USD"),
            }
            send_notification_email_async.delay(
                schema_name=schema_name,
                recipient_email=email,
                subject=f"Reservation Cancelled — #{booking.booking_reference}",
                template_name="emails/booking_cancellation.html",
                context=context,
                event_key=event_key,
            )

        return in_app_notif, True

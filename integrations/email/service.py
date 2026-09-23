import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """
    Transactional email delivery service supporting tenant branding and HTML/text multi-alternatives.
    """

    @classmethod
    def send_template_email(
        cls,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
        from_email: str | None = None,
    ) -> bool:
        sender = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@platform.com")
        enriched_context = {
            "subject": subject,
            "company_name": context.get("company_name", "Luxury Car Rental SaaS"),
            "support_email": context.get("support_email", "support@platform.com"),
            "current_year": context.get("current_year", 2026),
            **context,
        }

        try:
            html_content = render_to_string(template_name, enriched_context)
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=sender,
                to=[to_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            logger.info(f"Email '{subject}' successfully dispatched to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch email '{subject}' to {to_email}: {e}")
            return False

    @classmethod
    def send_booking_confirmation(cls, booking: Any, recipient_email: str | None = None) -> bool:
        customer = getattr(booking, "customer", None)
        email = recipient_email or (customer.email if customer else None)
        if not email:
            logger.warning(f"No recipient email found for booking {getattr(booking, 'id', None)}")
            return False

        pickup_branch = getattr(booking, "pickup_branch", None)
        return_branch = getattr(booking, "return_branch", None)
        vehicle = getattr(booking, "vehicle", None)

        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}"
            if customer
            else "Valued Renter",
            "booking_reference": booking.booking_reference,
            "vehicle_name": f"{vehicle.brand} {vehicle.model} ({vehicle.year})"
            if vehicle
            else "Reserved Vehicle",
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

        subject = f"Booking Confirmed — #{booking.booking_reference}"
        return cls.send_template_email(
            to_email=email,
            subject=subject,
            template_name="emails/booking_confirmation.html",
            context=context,
        )

    @classmethod
    def send_payment_receipt(cls, payment: Any, recipient_email: str | None = None) -> bool:
        booking = getattr(payment, "booking", None)
        customer = getattr(booking, "customer", None) if booking else None
        email = recipient_email or (customer.email if customer else None)
        if not email:
            logger.warning(f"No recipient email found for payment {getattr(payment, 'id', None)}")
            return False

        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}"
            if customer
            else "Valued Renter",
            "payment_id": str(payment.id)[:8].upper(),
            "booking_reference": booking.booking_reference if booking else "N/A",
            "provider": payment.provider,
            "transaction_reference": payment.transaction_reference or "N/A",
            "payment_date": payment.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "status": payment.status,
        }

        subject = f"Payment Receipt — #{booking.booking_reference if booking else payment.id}"
        return cls.send_template_email(
            to_email=email,
            subject=subject,
            template_name="emails/payment_receipt.html",
            context=context,
        )

    @classmethod
    def send_booking_cancellation(
        cls,
        booking: Any,
        recipient_email: str | None = None,
        refund_amount: Decimal | None = None,
        reason: str | None = None,
    ) -> bool:
        customer = getattr(booking, "customer", None)
        email = recipient_email or (customer.email if customer else None)
        if not email:
            return False

        vehicle = getattr(booking, "vehicle", None)
        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}"
            if customer
            else "Valued Renter",
            "booking_reference": booking.booking_reference,
            "vehicle_name": f"{vehicle.brand} {vehicle.model}" if vehicle else "Vehicle",
            "cancellation_reason": reason or getattr(booking, "notes", ""),
            "refund_amount": f"{refund_amount:.2f}" if refund_amount else None,
            "currency": getattr(booking, "currency", "USD"),
        }

        subject = f"Reservation Cancelled — #{booking.booking_reference}"
        return cls.send_template_email(
            to_email=email,
            subject=subject,
            template_name="emails/booking_cancellation.html",
            context=context,
        )

    @classmethod
    def send_pickup_reminder(cls, booking: Any, recipient_email: str | None = None) -> bool:
        customer = getattr(booking, "customer", None)
        email = recipient_email or (customer.email if customer else None)
        if not email:
            return False

        pickup_branch = getattr(booking, "pickup_branch", None)
        vehicle = getattr(booking, "vehicle", None)
        context = {
            "customer_name": f"{customer.first_name} {customer.last_name}"
            if customer
            else "Valued Renter",
            "booking_reference": booking.booking_reference,
            "vehicle_name": f"{vehicle.brand} {vehicle.model}" if vehicle else "Vehicle",
            "pickup_branch_address": getattr(pickup_branch, "address_line1", "Branch Depot"),
            "pickup_datetime": booking.pickup_datetime.strftime("%Y-%m-%d %H:%M UTC"),
        }

        subject = f"Reminder: Upcoming Vehicle Pickup — #{booking.booking_reference}"
        return cls.send_template_email(
            to_email=email,
            subject=subject,
            template_name="emails/pickup_reminder.html",
            context=context,
        )

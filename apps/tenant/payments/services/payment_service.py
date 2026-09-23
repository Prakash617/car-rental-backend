import json
import logging
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.tenant.bookings.models import (
    Booking,
    BookingStatus,
    PaymentStatus,
)
from apps.tenant.notifications.services.notification_service import NotificationService
from apps.tenant.payments.models import (
    Payment,
    PaymentProviderChoices,
    PaymentStatusChoices,
    PaymentTypeChoices,
    WebhookEvent,
    WebhookStatusChoices,
)
from integrations.payments.base import PaymentIntentResult, RefundResult
from integrations.payments.factory import get_payment_provider

logger = logging.getLogger(__name__)


class InvalidWebhookSignatureError(Exception):
    """Raised when an incoming webhook signature does not match expectations."""

    pass


class PaymentService:
    """
    Central orchestration service for tenant payments, webhooks, idempotency protection,
    and booking state synchronization.
    """

    @classmethod
    def create_payment_intent(
        cls,
        booking: Booking,
        provider_name: str,
        amount: Decimal | None = None,
        payment_type: str = PaymentTypeChoices.RENTAL_CHARGE,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Payment, PaymentIntentResult]:
        """
        Creates a payment intent with the chosen payment gateway and persists an initial
        ledger entry in the tenant schema.
        """
        if booking.status in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
            raise ValueError(
                f"Cannot initiate payment for {booking.status} booking #{booking.booking_reference}"
            )

        # Idempotency check on client-provided key
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                logger.info(
                    f"Payment with idempotency key '{idempotency_key}' already exists: {existing.id}"
                )
                return existing, PaymentIntentResult(
                    success=True,
                    transaction_reference=existing.transaction_reference,
                    client_secret=existing.gateway_response.get("client_secret", ""),
                    redirect_url=existing.gateway_response.get("redirect_url", ""),
                    status=existing.status,
                    raw_response=existing.gateway_response,
                )

        charge_amount = amount if amount is not None else booking.total_price
        provider = get_payment_provider(provider_name)
        tenant = getattr(connection, "tenant", None)
        currency = getattr(booking, "currency", getattr(tenant, "currency", "USD"))

        intent_result = provider.create_intent(
            booking=booking,
            amount=charge_amount,
            currency=currency,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )

        with transaction.atomic():
            payment = Payment.objects.create(
                booking=booking,
                provider=provider_name,
                payment_type=payment_type,
                status=PaymentStatusChoices.PENDING,
                amount=charge_amount,
                currency=currency,
                transaction_reference=intent_result.transaction_reference,
                idempotency_key=idempotency_key,
                gateway_response=intent_result.raw_response,
            )

        return payment, intent_result

    @classmethod
    def process_webhook(
        cls,
        provider_name: str,
        payload_bytes: bytes,
        signature_header: str,
        secret: str | None = None,
    ) -> tuple[bool, str]:
        """
        Idempotently verifies and ingests incoming webhooks, transitioning payment
        and booking states accordingly.
        """
        provider = get_payment_provider(provider_name)

        # 1. Cryptographic Signature Verification
        is_valid = provider.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature_header=signature_header,
            secret=secret,
        )
        if not is_valid:
            logger.warning(f"Invalid webhook signature for provider: {provider_name}")
            raise InvalidWebhookSignatureError(f"Signature mismatch for {provider_name}")

        # 2. Parse Raw Payload
        try:
            payload_dict = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            payload_dict = {}

        event_data = provider.parse_webhook_event(payload_dict)

        # 3. Idempotency Check with WebhookEvent Ledger
        try:
            with transaction.atomic():
                webhook_event, created = WebhookEvent.objects.get_or_create(
                    provider=provider_name,
                    event_id=event_data.event_id,
                    defaults={
                        "event_type": event_data.event_type,
                        "payload": event_data.raw_payload,
                        "status": WebhookStatusChoices.RECEIVED,
                    },
                )
        except IntegrityError:
            # Concurrently inserted
            logger.info(
                f"Duplicate webhook {provider_name}:{event_data.event_id} already received."
            )
            return True, "Event already received"

        if not created and webhook_event.status == WebhookStatusChoices.PROCESSED:
            logger.info(
                f"Duplicate webhook {provider_name}:{event_data.event_id} already processed."
            )
            return True, "Event already processed"

        # 4. Resolve and Synchronize Payment and Booking
        try:
            with transaction.atomic():
                # Attempt to find payment by transaction_reference
                payment = None
                if event_data.transaction_reference:
                    payment = (
                        Payment.objects.select_for_update()
                        .filter(
                            provider=provider_name,
                            transaction_reference=event_data.transaction_reference,
                        )
                        .first()
                    )

                if not payment and event_data.booking_reference:
                    # Match by booking reference
                    booking = (
                        Booking.objects.select_for_update()
                        .filter(booking_reference=event_data.booking_reference)
                        .first()
                    )
                    if booking:
                        payment = (
                            Payment.objects.select_for_update()
                            .filter(booking=booking, provider=provider_name)
                            .first()
                        )

                if not payment:
                    logger.warning(
                        f"Webhook {event_data.event_id} could not find matching payment for "
                        f"ref={event_data.transaction_reference}, booking_ref={event_data.booking_reference}"
                    )
                    webhook_event.status = WebhookStatusChoices.IGNORED
                    webhook_event.error_message = "No matching payment record found"
                    webhook_event.save(update_fields=["status", "error_message"])
                    return True, "Ignored: No matching payment"

                booking = payment.booking

                # Transition statuses
                if event_data.status == "succeeded":
                    payment.status = PaymentStatusChoices.SUCCEEDED
                    payment.save(update_fields=["status", "updated_at"])

                    # Update booking payment status
                    paid_total = sum(
                        p.amount
                        for p in Payment.objects.filter(
                            booking=booking,
                            status=PaymentStatusChoices.SUCCEEDED,
                        )
                    )

                    if paid_total >= booking.total_price:
                        booking.payment_status = PaymentStatus.PAID
                    elif paid_total > Decimal("0.00"):
                        booking.payment_status = PaymentStatus.PARTIALLY_PAID

                    # If pending, transition to confirmed
                    if booking.status == BookingStatus.PENDING:
                        booking.status = BookingStatus.CONFIRMED

                    booking.save(update_fields=["payment_status", "status", "updated_at"])

                    # Dispatch notifications
                    NotificationService.dispatch_payment_receipt(payment)
                    NotificationService.dispatch_booking_confirmation(booking)

                elif event_data.status == "failed":
                    payment.status = PaymentStatusChoices.FAILED
                    payment.save(update_fields=["status", "updated_at"])

                elif event_data.status == "refunded":
                    payment.status = PaymentStatusChoices.REFUNDED
                    payment.save(update_fields=["status", "updated_at"])

                webhook_event.status = WebhookStatusChoices.PROCESSED
                webhook_event.processed_at = timezone.now()
                webhook_event.save(update_fields=["status", "processed_at"])

                logger.info(
                    f"Successfully processed webhook {provider_name}:{event_data.event_id} for "
                    f"Booking #{booking.booking_reference}"
                )
                return True, "Payment status synchronized"
        except Exception as e:
            logger.error(f"Error processing webhook {event_data.event_id}: {e}", exc_info=True)
            webhook_event.status = WebhookStatusChoices.FAILED
            webhook_event.error_message = str(e)
            webhook_event.save(update_fields=["status", "error_message"])
            raise

    @classmethod
    def record_manual_payment(
        cls,
        booking: Booking,
        amount: Decimal,
        provider: str = PaymentProviderChoices.CASH,
        reference: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> Payment:
        """
        Records an in-person cash or bank wire payment confirmed directly by staff.
        """
        with transaction.atomic():
            booking_locked = Booking.objects.select_for_update().get(id=booking.id)

            txn_ref = (
                reference
                or f"MANUAL_{booking_locked.booking_reference}_{int(timezone.now().timestamp())}"
            )

            tenant = getattr(connection, "tenant", None)
            currency = getattr(booking_locked, "currency", getattr(tenant, "currency", "USD"))

            payment = Payment.objects.create(
                booking=booking_locked,
                provider=provider,
                payment_type=PaymentTypeChoices.RENTAL_CHARGE,
                status=PaymentStatusChoices.SUCCEEDED,
                amount=amount,
                currency=currency,
                transaction_reference=txn_ref,
                idempotency_key=idempotency_key,
                gateway_response={"notes": notes or "Manual payment confirmed by staff"},
            )

            # Recompute total payments
            paid_total = sum(
                p.amount
                for p in Payment.objects.filter(
                    booking=booking_locked,
                    status=PaymentStatusChoices.SUCCEEDED,
                )
            )

            if paid_total >= booking_locked.total_price:
                booking_locked.payment_status = PaymentStatus.PAID
            elif paid_total > Decimal("0.00"):
                booking_locked.payment_status = PaymentStatus.PARTIALLY_PAID

            if booking_locked.status == BookingStatus.PENDING:
                booking_locked.status = BookingStatus.CONFIRMED

            booking_locked.save(update_fields=["payment_status", "status", "updated_at"])

            NotificationService.dispatch_payment_receipt(payment)
            if booking_locked.status == BookingStatus.CONFIRMED:
                NotificationService.dispatch_booking_confirmation(booking_locked)

            return payment

    @classmethod
    def refund_payment(
        cls,
        payment_id: str,
        amount: Decimal | None = None,
        reason: str | None = None,
    ) -> tuple[Payment, RefundResult]:
        """
        Executes a gateway refund for a previously captured payment.
        """
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id)
            if payment.status != PaymentStatusChoices.SUCCEEDED:
                raise ValueError(f"Cannot refund payment with status '{payment.status}'")

            refund_amount = amount if amount is not None else payment.amount
            provider = get_payment_provider(payment.provider)

            result = provider.refund(
                transaction_ref=payment.transaction_reference,
                amount=refund_amount,
                reason=reason,
            )

            if result.success:
                if refund_amount >= payment.amount:
                    payment.status = PaymentStatusChoices.REFUNDED
                else:
                    payment.status = PaymentStatusChoices.PARTIALLY_REFUNDED
                payment.save(update_fields=["status", "updated_at"])

            return payment, result

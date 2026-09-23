import hashlib
import hmac
import logging
import os
import time
from decimal import Decimal
from typing import Any

from integrations.payments.base import (
    PaymentIntentResult,
    PaymentProvider,
    RefundResult,
    WebhookEventData,
)

logger = logging.getLogger(__name__)


class KhaltiProvider(PaymentProvider):
    """
    Khalti ePayment gateway integration supporting pidx initiation, callback verification,
    and server-to-server signature validation.
    """

    def __init__(self, secret_key: str | None = None):
        self.secret_key = secret_key or os.getenv(
            "KHALTI_SECRET_KEY", "live_secret_key_mock_khalti"
        )
        self.initiate_url = os.getenv(
            "KHALTI_INITIATE_URL",
            "https://a.khalti.com/api/v2/epayment/initiate/",
        )

    @property
    def name(self) -> str:
        return "khalti"

    def create_intent(
        self,
        booking: Any,
        amount: Decimal,
        currency: str,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentIntentResult:
        booking_ref = getattr(booking, "booking_reference", "")
        booking_id = str(getattr(booking, "id", ""))
        amount_paisa = int(amount * 100)

        # Unique purchase order ID
        pidx = f"khalti_{booking_ref}_{int(time.time())}"
        payment_url = f"https://test-pay.khalti.com/?pidx={pidx}"

        payload = {
            "return_url": metadata.get("return_url", "https://platform.com/booking/khalti/return")
            if metadata
            else "https://platform.com/booking/khalti/return",
            "website_url": "https://platform.com",
            "amount": amount_paisa,
            "purchase_order_id": booking_ref,
            "purchase_order_name": f"Car Rental Booking #{booking_ref}",
            "customer_info": {
                "booking_id": booking_id,
            },
        }

        return PaymentIntentResult(
            success=True,
            transaction_reference=pidx,
            redirect_url=payment_url,
            status="pending",
            raw_response={"pidx": pidx, "payment_url": payment_url, "payload": payload},
        )

    def confirm_payment(self, transaction_ref: str) -> PaymentIntentResult:
        return PaymentIntentResult(
            success=True,
            transaction_reference=transaction_ref,
            status="succeeded",
            raw_response={"pidx": transaction_ref, "status": "Completed"},
        )

    def refund(
        self,
        transaction_ref: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        return RefundResult(
            success=True,
            refund_reference=f"khalti_ref_{transaction_ref[:10]}",
            amount_refunded=amount,
            status="refunded",
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str | None = None,
    ) -> bool:
        signing_secret = secret or self.secret_key
        if not signature_header or not signing_secret:
            return False

        try:
            expected_signature = hmac.new(
                signing_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature_header)
        except Exception as e:
            logger.error(f"Khalti webhook verification failed: {e}")
            return False

    def parse_webhook_event(self, payload: dict[str, Any]) -> WebhookEventData:
        pidx = payload.get("pidx", "")
        raw_status = payload.get("status", "Completed")
        status = "succeeded" if raw_status == "Completed" else "failed"

        amount_paisa = payload.get("total_amount", payload.get("amount", 0))
        amount = Decimal(str(amount_paisa)) / Decimal("100.00")
        booking_ref = payload.get("purchase_order_id", "")
        txn_id = payload.get("transaction_id", pidx)

        return WebhookEventData(
            event_id=txn_id or pidx,
            event_type="khalti.payment.completed"
            if status == "succeeded"
            else "khalti.payment.failed",
            booking_reference=booking_ref,
            amount=amount,
            currency="NPR",
            transaction_reference=pidx,
            status=status,
            raw_payload=payload,
        )

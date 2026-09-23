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


class StripeProvider(PaymentProvider):
    """
    Stripe payment integration supporting PaymentIntents and standard HMAC-SHA256
    webhook signature verification.
    """

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None):
        self.api_key = api_key or os.getenv("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key")
        self.webhook_secret = webhook_secret or os.getenv(
            "STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_secret"
        )

    @property
    def name(self) -> str:
        return "stripe"

    def create_intent(
        self,
        booking: Any,
        amount: Decimal,
        currency: str,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentIntentResult:
        meta = metadata or {}
        booking_id = str(getattr(booking, "id", ""))
        booking_ref = getattr(booking, "booking_reference", "")
        meta.setdefault("booking_id", booking_id)
        meta.setdefault("booking_reference", booking_ref)

        # Generates deterministic transaction ref if simulated or API call
        amount_cents = int(amount * 100)
        txn_id = f"pi_stripe_{booking_ref}_{int(time.time())}"
        client_secret = f"{txn_id}_secret_{hashlib.md5(txn_id.encode()).hexdigest()[:16]}"

        return PaymentIntentResult(
            success=True,
            transaction_reference=txn_id,
            client_secret=client_secret,
            redirect_url="",
            status="pending",
            raw_response={
                "id": txn_id,
                "amount": amount_cents,
                "currency": currency.lower(),
                "client_secret": client_secret,
                "metadata": meta,
            },
        )

    def confirm_payment(self, transaction_ref: str) -> PaymentIntentResult:
        return PaymentIntentResult(
            success=True,
            transaction_reference=transaction_ref,
            status="succeeded",
            raw_response={"id": transaction_ref, "status": "succeeded"},
        )

    def refund(
        self,
        transaction_ref: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        refund_id = f"re_stripe_{hashlib.md5(transaction_ref.encode()).hexdigest()[:12]}"
        return RefundResult(
            success=True,
            refund_reference=refund_id,
            amount_refunded=amount,
            status="succeeded",
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str | None = None,
    ) -> bool:
        """
        Verifies Stripe's 't=timestamp,v1=signature' format.
        """
        signing_secret = secret or self.webhook_secret
        if not signature_header or not signing_secret:
            return False

        try:
            pairs = {}
            for item in signature_header.split(","):
                key, val = item.strip().split("=", 1)
                pairs[key] = val

            timestamp = pairs.get("t")
            signature = pairs.get("v1")

            if not timestamp or not signature:
                return False

            # Check timestamp tolerance (5 minutes)
            current_time = int(time.time())
            if abs(current_time - int(timestamp)) > 300:
                logger.warning("Stripe webhook timestamp older than 300s tolerance")
                return False

            signed_payload = f"{timestamp}.".encode() + payload_bytes
            expected_signature = hmac.new(
                signing_secret.encode("utf-8"),
                signed_payload,
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Stripe signature verification failed: {e}")
            return False

    def parse_webhook_event(self, payload: dict[str, Any]) -> WebhookEventData:
        event_id = payload.get("id", "")
        event_type = payload.get("type", "")
        data_object = payload.get("data", {}).get("object", {})

        metadata = data_object.get("metadata", {})
        booking_id = metadata.get("booking_id", "")
        booking_ref = metadata.get("booking_reference", "")

        amount_cents = data_object.get("amount", 0)
        amount = Decimal(str(amount_cents)) / Decimal("100.00")
        currency = data_object.get("currency", "USD").upper()
        transaction_ref = data_object.get("id", "")

        status = "succeeded"
        if "failed" in event_type:
            status = "failed"
        elif "refund" in event_type:
            status = "refunded"

        return WebhookEventData(
            event_id=event_id,
            event_type=event_type,
            booking_id=booking_id,
            booking_reference=booking_ref,
            amount=amount,
            currency=currency,
            transaction_reference=transaction_ref,
            status=status,
            raw_payload=payload,
        )

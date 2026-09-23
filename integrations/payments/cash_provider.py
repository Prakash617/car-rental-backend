import hashlib
import time
from decimal import Decimal
from typing import Any

from integrations.payments.base import (
    PaymentIntentResult,
    PaymentProvider,
    RefundResult,
    WebhookEventData,
)


class CashBankProvider(PaymentProvider):
    """
    Handles in-person cash payments and manual direct bank wire transfers.
    Transactions are validated and recorded directly by authorized staff members.
    """

    def __init__(self, provider_type: str = "cash"):
        self._provider_type = provider_type

    @property
    def name(self) -> str:
        return self._provider_type

    def create_intent(
        self,
        booking: Any,
        amount: Decimal,
        currency: str,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentIntentResult:
        booking_ref = getattr(booking, "booking_reference", "REF")
        txn_ref = f"{self._provider_type.upper()}_{booking_ref}_{int(time.time())}"

        return PaymentIntentResult(
            success=True,
            transaction_reference=txn_ref,
            status="pending",
            raw_response={
                "provider": self._provider_type,
                "transaction_reference": txn_ref,
                "notes": "Awaiting in-person cash collection or wire confirmation",
            },
        )

    def confirm_payment(self, transaction_ref: str) -> PaymentIntentResult:
        return PaymentIntentResult(
            success=True,
            transaction_reference=transaction_ref,
            status="succeeded",
            raw_response={"status": "confirmed_manually"},
        )

    def refund(
        self,
        transaction_ref: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        ref_id = (
            f"refund_{self._provider_type}_{hashlib.md5(transaction_ref.encode()).hexdigest()[:8]}"
        )
        return RefundResult(
            success=True,
            refund_reference=ref_id,
            amount_refunded=amount,
            status="refunded",
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str | None = None,
    ) -> bool:
        # Cash/bank is manual, does not receive webhook from third party
        return False

    def parse_webhook_event(self, payload: dict[str, Any]) -> WebhookEventData:
        return WebhookEventData(
            event_id=payload.get("event_id", ""),
            event_type="manual.payment.recorded",
            amount=Decimal(str(payload.get("amount", "0.00"))),
            currency=payload.get("currency", "USD"),
            transaction_reference=payload.get("transaction_reference", ""),
            status="succeeded",
            raw_payload=payload,
        )

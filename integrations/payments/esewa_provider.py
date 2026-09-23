import base64
import hashlib
import hmac
import json
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


class EsewaProvider(PaymentProvider):
    """
    eSewa EPAY v2 payment integration for Nepal currency (NPR/USD equivalent).
    Supports base64 HMAC-SHA256 signature verification and checkout redirect payloads.
    """

    def __init__(self, secret_key: str | None = None, product_code: str | None = None):
        self.secret_key = secret_key or os.getenv("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
        self.product_code = product_code or os.getenv("ESEWA_PRODUCT_CODE", "EPAYTEST")
        self.gateway_url = os.getenv(
            "ESEWA_GATEWAY_URL",
            "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
        )

    @property
    def name(self) -> str:
        return "esewa"

    def _generate_signature(self, message: str, secret: str) -> str:
        h = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        return base64.b64encode(h.digest()).decode("utf-8")

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
        txn_uuid = f"esewa_{booking_ref}_{int(time.time())}"

        # eSewa v2 signature message: total_amount,transaction_uuid,product_code
        total_amount_str = f"{amount:.2f}"
        message = f"total_amount={total_amount_str},transaction_uuid={txn_uuid},product_code={self.product_code}"
        signature = self._generate_signature(message, self.secret_key)

        payload = {
            "amount": total_amount_str,
            "tax_amount": "0",
            "total_amount": total_amount_str,
            "transaction_uuid": txn_uuid,
            "product_code": self.product_code,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": metadata.get("success_url", "https://platform.com/booking/success")
            if metadata
            else "https://platform.com/booking/success",
            "failure_url": metadata.get("failure_url", "https://platform.com/booking/failure")
            if metadata
            else "https://platform.com/booking/failure",
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": signature,
            "booking_id": booking_id,
        }

        return PaymentIntentResult(
            success=True,
            transaction_reference=txn_uuid,
            redirect_url=self.gateway_url,
            status="pending",
            raw_response=payload,
        )

    def confirm_payment(self, transaction_ref: str) -> PaymentIntentResult:
        return PaymentIntentResult(
            success=True,
            transaction_reference=transaction_ref,
            status="succeeded",
            raw_response={"transaction_code": transaction_ref, "status": "COMPLETE"},
        )

    def refund(
        self,
        transaction_ref: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        return RefundResult(
            success=True,
            refund_reference=f"esewa_ref_{transaction_ref[:10]}",
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
        try:
            # Handle either JSON body or raw decoded data
            data = json.loads(payload_bytes.decode("utf-8"))
            encoded_data = data.get("data")
            if encoded_data:
                decoded_str = base64.b64decode(encoded_data).decode("utf-8")
                parsed_data = json.loads(decoded_str)
            else:
                parsed_data = data

            received_sig = parsed_data.get("signature") or signature_header
            total_amount = parsed_data.get("total_amount")
            txn_uuid = parsed_data.get("transaction_uuid")
            product_code = parsed_data.get("product_code", self.product_code)

            if not (received_sig and total_amount and txn_uuid):
                return False

            message = f"total_amount={total_amount},transaction_uuid={txn_uuid},product_code={product_code}"
            expected_sig = self._generate_signature(message, signing_secret)
            return hmac.compare_digest(expected_sig, received_sig)
        except Exception as e:
            logger.error(f"eSewa webhook verification failed: {e}")
            return False

    def parse_webhook_event(self, payload: dict[str, Any]) -> WebhookEventData:
        encoded_data = payload.get("data")
        if encoded_data:
            decoded_str = base64.b64decode(encoded_data).decode("utf-8")
            data = json.loads(decoded_str)
        else:
            data = payload

        txn_uuid = data.get("transaction_uuid", "")
        # Transaction UUID format: esewa_{booking_ref}_{timestamp}
        booking_ref = ""
        if txn_uuid.startswith("esewa_"):
            parts = txn_uuid.split("_")
            if len(parts) >= 2:
                booking_ref = parts[1]

        amount_str = str(data.get("total_amount", "0.00")).replace(",", "")
        amount = Decimal(amount_str)
        raw_status = data.get("status", "COMPLETE").upper()
        status = "succeeded" if raw_status in ("COMPLETE", "SUCCESS") else "failed"

        return WebhookEventData(
            event_id=data.get("transaction_code", txn_uuid),
            event_type="payment.completed" if status == "succeeded" else "payment.failed",
            booking_id=data.get("booking_id", ""),
            booking_reference=booking_ref,
            amount=amount,
            currency="NPR",
            transaction_reference=txn_uuid,
            status=status,
            raw_payload=data,
        )

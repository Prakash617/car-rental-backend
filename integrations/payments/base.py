from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class PaymentIntentResult:
    success: bool
    transaction_reference: str
    client_secret: str = ""
    redirect_url: str = ""
    status: str = "pending"
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class WebhookEventData:
    event_id: str
    event_type: str
    booking_id: str = ""
    booking_reference: str = ""
    amount: Decimal = Decimal("0.00")
    currency: str = "USD"
    transaction_reference: str = ""
    status: str = "succeeded"  # succeeded, failed, refunded
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    success: bool
    refund_reference: str
    amount_refunded: Decimal = Decimal("0.00")
    status: str = "succeeded"
    error: str = ""


class PaymentProvider(ABC):
    """
    Abstract Base Class defining the contract for all car rental payment providers.
    Supports tokenized direct intents, hosted redirects, and manual bank/cash workflows.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier code (e.g. 'stripe', 'esewa', 'khalti', 'cash')."""
        pass

    @abstractmethod
    def create_intent(
        self,
        booking: Any,
        amount: Decimal,
        currency: str,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentIntentResult:
        """Create a payment intent or checkout session."""
        pass

    @abstractmethod
    def confirm_payment(self, transaction_ref: str) -> PaymentIntentResult:
        """Query or confirm payment status directly with the gateway."""
        pass

    @abstractmethod
    def refund(
        self,
        transaction_ref: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        """Process a refund for a previously captured payment."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str | None = None,
    ) -> bool:
        """Cryptographically verify authenticity of incoming gateway webhook."""
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: dict[str, Any]) -> WebhookEventData:
        """Parse raw gateway webhook payload into standardized WebhookEventData."""
        pass

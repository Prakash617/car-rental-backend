import base64
import hashlib
import hmac
import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from integrations.payments.cash_provider import CashBankProvider
from integrations.payments.esewa_provider import EsewaProvider
from integrations.payments.factory import get_payment_provider
from integrations.payments.khalti_provider import KhaltiProvider
from integrations.payments.stripe_provider import StripeProvider


@pytest.fixture
def mock_booking():
    booking = MagicMock()
    booking.id = "00000000-0000-0000-0000-000000000001"
    booking.booking_reference = "BK-TEST999"
    booking.currency = "USD"
    booking.total_price = Decimal("250.00")
    return booking


class TestPaymentProviders:
    def test_factory_resolves_valid_providers(self):
        assert isinstance(get_payment_provider("stripe"), StripeProvider)
        assert isinstance(get_payment_provider("esewa"), EsewaProvider)
        assert isinstance(get_payment_provider("khalti"), KhaltiProvider)
        assert isinstance(get_payment_provider("cash"), CashBankProvider)
        assert isinstance(get_payment_provider("bank_transfer"), CashBankProvider)

    def test_factory_rejects_invalid_provider(self):
        with pytest.raises(ValueError, match="Unsupported payment provider"):
            get_payment_provider("bitcoin")

    def test_stripe_create_intent(self, mock_booking):
        provider = StripeProvider()
        result = provider.create_intent(
            booking=mock_booking,
            amount=Decimal("250.00"),
            currency="USD",
        )
        assert result.success is True
        assert result.transaction_reference.startswith("pi_stripe_BK-TEST999")
        assert result.client_secret is not None
        assert result.status == "pending"

    def test_stripe_signature_verification_valid(self):
        secret = "whsec_test_secret_key"
        provider = StripeProvider(webhook_secret=secret)

        now = int(time.time())
        payload = b'{"id": "evt_test_123", "type": "payment_intent.succeeded"}'
        signed_payload = f"{now}.".encode() + payload
        signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        header = f"t={now},v1={signature}"

        assert provider.verify_webhook_signature(payload, header, secret=secret) is True

    def test_stripe_signature_verification_tampered_fails(self):
        secret = "whsec_test_secret_key"
        provider = StripeProvider(webhook_secret=secret)

        now = int(time.time())
        payload = b'{"id": "evt_test_123", "type": "payment_intent.succeeded"}'
        tampered_payload = b'{"id": "evt_test_123", "type": "payment_intent.tampered"}'
        signed_payload = f"{now}.".encode() + payload
        signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        header = f"t={now},v1={signature}"

        assert provider.verify_webhook_signature(tampered_payload, header, secret=secret) is False

    def test_stripe_signature_verification_expired_timestamp_fails(self):
        secret = "whsec_test_secret_key"
        provider = StripeProvider(webhook_secret=secret)

        expired_time = int(time.time()) - 400  # older than 300s tolerance
        payload = b'{"id": "evt_test_123"}'
        signed_payload = f"{expired_time}.".encode() + payload
        signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        header = f"t={expired_time},v1={signature}"

        assert provider.verify_webhook_signature(payload, header, secret=secret) is False

    def test_esewa_create_intent_and_signature(self, mock_booking):
        secret = "8gBm/:&EnhH.1/q"
        product_code = "EPAYTEST"
        provider = EsewaProvider(secret_key=secret, product_code=product_code)

        result = provider.create_intent(
            booking=mock_booking,
            amount=Decimal("15000.00"),
            currency="NPR",
        )
        assert result.success is True
        assert result.redirect_url == provider.gateway_url
        assert "signature" in result.raw_response

        # Verify signature generated matches HMAC-SHA256
        raw = result.raw_response
        message = f"total_amount={raw['total_amount']},transaction_uuid={raw['transaction_uuid']},product_code={product_code}"
        expected_sig = base64.b64encode(
            hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        assert raw["signature"] == expected_sig

    def test_esewa_webhook_signature_verification(self):
        secret = "8gBm/:&EnhH.1/q"
        product_code = "EPAYTEST"
        provider = EsewaProvider(secret_key=secret, product_code=product_code)

        total_amount = "15000.00"
        txn_uuid = "esewa_BK-TEST999_12345"
        message = (
            f"total_amount={total_amount},transaction_uuid={txn_uuid},product_code={product_code}"
        )
        signature = base64.b64encode(
            hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()

        payload = f'{{"total_amount": "{total_amount}", "transaction_uuid": "{txn_uuid}", "product_code": "{product_code}", "signature": "{signature}"}}'.encode()
        assert provider.verify_webhook_signature(payload, signature, secret=secret) is True

    def test_khalti_create_intent(self, mock_booking):
        provider = KhaltiProvider()
        result = provider.create_intent(
            booking=mock_booking,
            amount=Decimal("5000.00"),
            currency="NPR",
        )
        assert result.success is True
        assert result.redirect_url.startswith("https://test-pay.khalti.com/?pidx=")
        assert result.transaction_reference.startswith("khalti_BK-TEST999")

    def test_cash_provider_flow(self, mock_booking):
        provider = CashBankProvider(provider_type="cash")
        intent = provider.create_intent(mock_booking, Decimal("100.00"), "USD")
        assert intent.success is True
        assert intent.transaction_reference.startswith("CASH_BK-TEST999")

        confirm = provider.confirm_payment(intent.transaction_reference)
        assert confirm.success is True
        assert confirm.status == "succeeded"

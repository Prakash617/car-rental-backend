import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from apps.tenant.bookings.models import Booking, BookingStatus, PaymentStatus
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.payments.models import (
    Payment,
    PaymentProviderChoices,
    PaymentStatusChoices,
    WebhookEvent,
    WebhookStatusChoices,
)
from apps.tenant.payments.services.payment_service import (
    InvalidWebhookSignatureError,
    PaymentService,
)
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus


@pytest.fixture
def sample_booking(tenant_a):
    with schema_context(tenant_a.schema_name):
        branch = Branch.objects.create(
            name="Alpha Airport",
            code="AERO",
            city="Kathmandu",
            country="NP",
            phone="+977-1-4000000",
            email="airport@alpha.com",
        )
        vehicle = Vehicle.objects.create(
            branch=branch,
            brand="Mercedes-Benz",
            model="G63 AMG",
            year=2024,
            license_plate="LUX-001",
            category=VehicleCategory.LUXURY,
            daily_rate=Decimal("500.00"),
            status=VehicleStatus.AVAILABLE,
        )
        customer = Customer.objects.create(
            first_name="Elon",
            last_name="Musk",
            email="elon@x.com",
            phone="+1-555-0999",
            driver_license_number="DL-US-9999",
            license_expiry_date="2030-01-01",
            date_of_birth="1971-06-28",
            country="US",
        )
        now = datetime.now(tz=UTC)
        booking = Booking.objects.create(
            booking_reference="BK-PAY100",
            vehicle=vehicle,
            customer=customer,
            pickup_branch=branch,
            return_branch=branch,
            pickup_datetime=now + timedelta(days=2),
            return_datetime=now + timedelta(days=5),
            base_price=Decimal("1500.00"),
            tax_amount=Decimal("150.00"),
            deposit_amount=Decimal("1000.00"),
            total_price=Decimal("1650.00"),
            status=BookingStatus.PENDING,
            payment_status=PaymentStatus.UNPAID,
        )
        return booking


@pytest.mark.django_db
class TestPaymentService:
    def test_create_payment_intent_success(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            payment, intent = PaymentService.create_payment_intent(
                booking=sample_booking,
                provider_name="stripe",
            )

            assert payment.status == PaymentStatusChoices.PENDING
            assert payment.amount == sample_booking.total_price
            assert payment.currency == "USD"
            assert intent.transaction_reference.startswith("pi_stripe_BK-PAY100")
            assert intent.client_secret is not None

    def test_create_payment_intent_idempotency_key(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            key = "idemp_test_token_unique_123"

            p1, intent1 = PaymentService.create_payment_intent(
                booking=sample_booking,
                provider_name="stripe",
                idempotency_key=key,
            )

            # Repeat with identical idempotency key
            p2, intent2 = PaymentService.create_payment_intent(
                booking=sample_booking,
                provider_name="stripe",
                idempotency_key=key,
            )

            # Must return exact same payment record
            assert p1.id == p2.id
            assert Payment.objects.filter(idempotency_key=key).count() == 1

    def test_process_webhook_succeeded_transitions_booking(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            payment, intent = PaymentService.create_payment_intent(
                booking=sample_booking,
                provider_name="stripe",
            )
            txn_ref = payment.transaction_reference

            # Construct valid Stripe webhook payload & signature
            secret = "whsec_mock_stripe_secret"
            event_id = f"evt_test_{int(time.time())}"
            now = int(time.time())
            amount_cents = int(sample_booking.total_price * 100)

            payload_json = (
                f'{{"id": "{event_id}", "type": "payment_intent.succeeded", '
                f'"data": {{"object": {{"id": "{txn_ref}", "amount": {amount_cents}, '
                f'"currency": "usd", "metadata": {{"booking_id": "{sample_booking.id}", '
                f'"booking_reference": "{sample_booking.booking_reference}"}}}}}}}}'
            ).encode()

            signed = f"{now}.".encode() + payload_json
            sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
            header = f"t={now},v1={sig}"

            success, message = PaymentService.process_webhook(
                provider_name="stripe",
                payload_bytes=payload_json,
                signature_header=header,
                secret=secret,
            )

            assert success is True

            # Verify Payment transitioned to SUCCEEDED
            payment.refresh_from_db()
            assert payment.status == PaymentStatusChoices.SUCCEEDED

            # Verify Booking transitioned to CONFIRMED and PAID
            sample_booking.refresh_from_db()
            assert sample_booking.status == BookingStatus.CONFIRMED
            assert sample_booking.payment_status == PaymentStatus.PAID

            # Verify WebhookEvent ledger recorded
            webhook_evt = WebhookEvent.objects.get(event_id=event_id)
            assert webhook_evt.status == WebhookStatusChoices.PROCESSED

    def test_process_webhook_replay_attack_defense(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            payment, intent = PaymentService.create_payment_intent(
                booking=sample_booking,
                provider_name="stripe",
            )
            txn_ref = payment.transaction_reference
            secret = "whsec_mock_stripe_secret"
            event_id = "evt_replay_defense_test_456"
            now = int(time.time())
            amount_cents = int(sample_booking.total_price * 100)

            payload_json = (
                f'{{"id": "{event_id}", "type": "payment_intent.succeeded", '
                f'"data": {{"object": {{"id": "{txn_ref}", "amount": {amount_cents}, '
                f'"currency": "usd", "metadata": {{"booking_id": "{sample_booking.id}", '
                f'"booking_reference": "{sample_booking.booking_reference}"}}}}}}}}'
            ).encode()

            signed = f"{now}.".encode() + payload_json
            sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
            header = f"t={now},v1={sig}"

            # 1. First execution
            success1, msg1 = PaymentService.process_webhook(
                "stripe", payload_json, header, secret=secret
            )
            assert success1 is True

            # 2. Replay attack: send identical event again
            success2, msg2 = PaymentService.process_webhook(
                "stripe", payload_json, header, secret=secret
            )
            assert success2 is True
            assert "already" in msg2.lower()

            # Verify exactly 1 webhook event recorded in ledger
            assert WebhookEvent.objects.filter(event_id=event_id).count() == 1

    def test_process_webhook_invalid_signature_rejected(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            payload_json = b'{"id": "evt_tampered", "type": "payment_intent.succeeded"}'
            invalid_header = "t=12345,v1=bad_signature_digest"

            with pytest.raises(InvalidWebhookSignatureError):
                PaymentService.process_webhook(
                    provider_name="stripe",
                    payload_bytes=payload_json,
                    signature_header=invalid_header,
                )

    def test_record_manual_payment(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            # Record partial cash payment
            partial_amount = Decimal("500.00")
            payment = PaymentService.record_manual_payment(
                booking=sample_booking,
                amount=partial_amount,
                provider=PaymentProviderChoices.CASH,
                reference="CASH-RECEIPT-001",
                notes="Paid in desk cash",
            )

            assert payment.status == PaymentStatusChoices.SUCCEEDED
            assert payment.amount == partial_amount

            sample_booking.refresh_from_db()
            assert sample_booking.status == BookingStatus.CONFIRMED
            assert sample_booking.payment_status == PaymentStatus.PARTIALLY_PAID

            # Record remainder
            remaining = sample_booking.total_price - partial_amount
            PaymentService.record_manual_payment(
                booking=sample_booking,
                amount=remaining,
                provider=PaymentProviderChoices.BANK_TRANSFER,
                reference="WIRE-REF-998",
            )

            sample_booking.refresh_from_db()
            assert sample_booking.payment_status == PaymentStatus.PAID

    def test_refund_payment_flow(self, tenant_a, sample_booking):
        with schema_context(tenant_a.schema_name):
            payment = PaymentService.record_manual_payment(
                booking=sample_booking,
                amount=sample_booking.total_price,
                provider=PaymentProviderChoices.CASH,
            )

            updated_payment, refund_result = PaymentService.refund_payment(
                payment_id=payment.id,
                reason="Customer requested cancellation",
            )

            assert refund_result.success is True
            assert updated_payment.status == PaymentStatusChoices.REFUNDED

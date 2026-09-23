from decimal import Decimal

from rest_framework import serializers

from apps.tenant.payments.models import (
    Payment,
    PaymentProviderChoices,
    PaymentTypeChoices,
    SecurityDeposit,
)


class PaymentSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "booking",
            "booking_reference",
            "provider",
            "payment_type",
            "status",
            "amount",
            "currency",
            "transaction_reference",
            "idempotency_key",
            "gateway_response",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreateCheckoutSessionSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(required=True)
    provider = serializers.ChoiceField(
        choices=PaymentProviderChoices.choices,
        default=PaymentProviderChoices.STRIPE,
    )
    payment_type = serializers.ChoiceField(
        choices=PaymentTypeChoices.choices,
        default=PaymentTypeChoices.RENTAL_CHARGE,
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.01"),
    )
    idempotency_key = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
    )
    success_url = serializers.URLField(required=False)
    failure_url = serializers.URLField(required=False)


class ManualPaymentSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal("0.01"),
    )
    provider = serializers.ChoiceField(
        choices=[
            (PaymentProviderChoices.CASH, "Cash"),
            (PaymentProviderChoices.BANK_TRANSFER, "Bank Transfer"),
        ],
        default=PaymentProviderChoices.CASH,
    )
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class RefundPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.01"),
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class SecurityDepositSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)

    class Meta:
        model = SecurityDeposit
        fields = [
            "id",
            "booking",
            "booking_reference",
            "hold_reference",
            "amount",
            "currency",
            "status",
            "captured_amount",
            "released_amount",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenant.bookings.models import Booking
from apps.tenant.payments.models import Payment
from apps.tenant.payments.serializers import (
    CreateCheckoutSessionSerializer,
    ManualPaymentSerializer,
    PaymentSerializer,
    RefundPaymentSerializer,
)
from apps.tenant.payments.services.payment_service import (
    InvalidWebhookSignatureError,
    PaymentService,
)
from common.permissions.tenant import (
    IsTenantManagerOrAbove,
    IsTenantMember,
    IsTenantStaffOrAbove,
)
from common.responses.standard import StandardResponseMixin

logger = logging.getLogger(__name__)


class CheckoutSessionView(StandardResponseMixin, APIView):
    """
    Initiates a payment intent or checkout session for a rental booking.
    Accessible publicly or by authenticated users.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=CreateCheckoutSessionSerializer)
    def post(self, request, *args, **kwargs):
        serializer = CreateCheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            booking = Booking.objects.get(id=data["booking_id"])
        except Booking.DoesNotExist:
            return self.error_response(
                message="Booking not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        metadata = {}
        if "success_url" in data:
            metadata["success_url"] = data["success_url"]
        if "failure_url" in data:
            metadata["failure_url"] = data["failure_url"]

        try:
            payment, intent_result = PaymentService.create_payment_intent(
                booking=booking,
                provider_name=data["provider"],
                amount=data.get("amount"),
                payment_type=data["payment_type"],
                idempotency_key=data.get("idempotency_key"),
                metadata=metadata,
            )
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return self.success_response(
            data={
                "payment": PaymentSerializer(payment).data,
                "checkout": {
                    "client_secret": intent_result.client_secret,
                    "redirect_url": intent_result.redirect_url,
                    "transaction_reference": intent_result.transaction_reference,
                    "status": intent_result.status,
                },
            },
            message="Payment checkout session created successfully",
            status_code=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class WebhookIngressView(APIView):
    """
    Untrusted external gateway ingress for incoming payment webhooks.
    Enforces cryptographic signature verification and idempotency defense.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, provider, *args, **kwargs):
        payload_bytes = request.body

        # Header resolution per provider
        signature_header = ""
        if provider == "stripe":
            signature_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        elif provider == "esewa":
            signature_header = request.META.get("HTTP_X_ESEWA_SIGNATURE", "")
        elif provider == "khalti":
            signature_header = request.META.get("HTTP_X_KHALTI_SIGNATURE", "")

        try:
            success, message = PaymentService.process_webhook(
                provider_name=provider,
                payload_bytes=payload_bytes,
                signature_header=signature_header,
            )
            return Response(
                {"status": "success", "message": message},
                status=status.HTTP_200_OK,
            )
        except InvalidWebhookSignatureError as e:
            logger.warning(f"Webhook signature rejected: {e}")
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            logger.warning(f"Unsupported provider: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Webhook processing failure: {e}", exc_info=True)
            return Response(
                {"error": "Internal webhook processing error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentViewSet(StandardResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve payment ledger transactions within the active tenant.
    """

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    filterset_fields = ["provider", "status", "payment_type", "booking"]
    search_fields = [
        "transaction_reference",
        "booking__booking_reference",
        "booking__customer__email",
        "booking__customer__last_name",
    ]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Payment.objects.select_related("booking", "booking__customer")

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[
            permissions.IsAuthenticated,
            IsTenantManagerOrAbove,
        ],
    )
    def refund(self, request, pk=None):
        serializer = RefundPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment, result = PaymentService.refund_payment(
                payment_id=pk,
                amount=data.get("amount"),
                reason=data.get("reason"),
            )
            return self.success_response(
                data={
                    "payment": PaymentSerializer(payment).data,
                    "refund_reference": result.refund_reference,
                    "amount_refunded": str(result.amount_refunded),
                },
                message="Payment refunded successfully",
            )
        except ValueError as e:
            return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)


class ManualPaymentView(StandardResponseMixin, APIView):
    """
    Records in-person cash or wire payments directly by tenant staff.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsTenantStaffOrAbove,
    ]

    @extend_schema(request=ManualPaymentSerializer)
    def post(self, request, *args, **kwargs):
        serializer = ManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            booking = Booking.objects.get(id=data["booking_id"])
        except Booking.DoesNotExist:
            return self.error_response(
                message="Booking not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        payment = PaymentService.record_manual_payment(
            booking=booking,
            amount=data["amount"],
            provider=data["provider"],
            reference=data.get("reference"),
            notes=data.get("notes"),
        )

        return self.success_response(
            data=PaymentSerializer(payment).data,
            message="Manual payment recorded successfully",
            status_code=status.HTTP_201_CREATED,
        )

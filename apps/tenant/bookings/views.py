from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenant.pricing.services.calculator import PricingCalculatorService
from apps.tenant.vehicles.models import Vehicle
from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Booking
from .serializers import (
    BookingSerializer,
    CreateBookingSerializer,
    QuoteRequestSerializer,
)
from .services.reservation import ReservationService


class QuoteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=QuoteRequestSerializer)
    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            vehicle = Vehicle.objects.get(id=data["vehicle_id"])
        except Vehicle.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "Vehicle not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        quote = PricingCalculatorService.calculate_quote(
            vehicle=vehicle,
            pickup_datetime=data["pickup_datetime"],
            return_datetime=data["return_datetime"],
            addon_ids=data.get("addon_ids"),
            coupon_code=data.get("coupon_code"),
        )
        return Response({"success": True, "data": quote})


class BookingViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Booking creation (open for public checkout) and management (staff only).
    """

    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]

    @extend_schema(request=CreateBookingSerializer, responses={201: BookingSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CreateBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        booking = ReservationService.create_reservation(
            vehicle_id=data["vehicle_id"],
            customer_data=data["customer"],
            pickup_branch_id=data["pickup_branch_id"],
            return_branch_id=data["return_branch_id"],
            pickup_datetime=data["pickup_datetime"],
            return_datetime=data["return_datetime"],
            addon_ids=data.get("addon_ids"),
            coupon_code=data.get("coupon_code"),
            notes=data.get("notes"),
        )

        return Response(
            {
                "success": True,
                "data": BookingSerializer(booking).data,
                "message": "Vehicle reservation initiated successfully.",
            },
            status=status.HTTP_201_CREATED,
        )

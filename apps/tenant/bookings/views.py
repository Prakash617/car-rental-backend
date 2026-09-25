from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.tenant.pricing.services.calculator import PricingCalculatorService
from apps.tenant.vehicles.models import Vehicle
from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Booking, BookingStatus
from .serializers import (
    BookingSerializer,
    CreateBookingSerializer,
    QuoteRequestSerializer,
)
from .services.reservation import ReservationService


class QuoteView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=QuoteRequestSerializer)
    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            vehicle = Vehicle.objects.get(id=data["vehicle_id"])
        except Vehicle.DoesNotExist:
            return self.error_response(
                message="Vehicle not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        quote = PricingCalculatorService.calculate_quote(
            vehicle=vehicle,
            pickup_datetime=data["pickup_datetime"],
            return_datetime=data["return_datetime"],
            addon_ids=data.get("addon_ids"),
            coupon_code=data.get("coupon_code"),
        )
        return self.success_response(data=quote)


class BookingViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Booking creation (open for public checkout) and lifecycle management (staff).
    Includes public lookup and cancellation.
    """

    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "status",
        "payment_status",
        "vehicle",
        "pickup_branch",
        "return_branch",
    ]
    search_fields = [
        "booking_reference",
        "customer__first_name",
        "customer__last_name",
        "customer__email",
        "vehicle__license_plate",
    ]
    ordering_fields = ["created_at", "pickup_datetime", "total_price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Booking.objects.select_related(
            "vehicle", "customer", "pickup_branch", "return_branch"
        ).prefetch_related("addons", "addons__addon")

    def get_permissions(self):
        if self.action in ["create", "lookup", "cancel"]:
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

        return self.success_response(
            data=BookingSerializer(booking).data,
            message="Vehicle reservation initiated successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="email",
                description="Customer email address for verification",
                required=False,
                type=str,
            )
        ],
        responses={200: BookingSerializer},
    )
    @action(detail=False, methods=["get"], url_path=r"lookup/(?P<reference>[^/.]+)")
    def lookup(self, request, reference=None):
        """
        Public lookup of reservation status using booking reference and email verification.
        """
        email = request.query_params.get("email")
        query = Booking.objects.select_related(
            "vehicle", "customer", "pickup_branch", "return_branch"
        ).filter(booking_reference__iexact=reference)

        if email:
            query = query.filter(customer__email__iexact=email.strip())

        booking = query.first()
        if not booking:
            return self.error_response(
                message="No booking found with this reference number and email.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return self.success_response(data=BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        Cancels a pending or confirmed booking.
        """
        booking = self.get_object()
        if booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
            return self.error_response(
                message=f"Cannot cancel booking with current status '{booking.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status"])

        # Release vehicle status back to available if it was reserved
        if booking.vehicle.status == "reserved":
            booking.vehicle.status = "available"
            booking.vehicle.save(update_fields=["status"])

        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=getattr(request.user, "email", "concierge@tenant.local"),
            action="CANCEL_BOOKING",
            resource_type="Booking",
            resource_id=str(booking.id),
            details={"reference": booking.booking_reference, "reason": request.data.get("reason", "")},
        )

        return self.success_response(
            data=BookingSerializer(booking).data,
            message="Booking cancelled successfully.",
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """
        Staff action to confirm a pending booking.
        """
        booking = self.get_object()
        if booking.status != BookingStatus.PENDING:
            return self.error_response(
                message=f"Cannot confirm booking with current status '{booking.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=["status"])
        if booking.vehicle.status == "available":
            booking.vehicle.status = "reserved"
            booking.vehicle.save(update_fields=["status"])

        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=getattr(request.user, "email", "concierge@tenant.local"),
            action="CONFIRM_BOOKING",
            resource_type="Booking",
            resource_id=str(booking.id),
            details={"reference": booking.booking_reference},
        )

        return self.success_response(
            data=BookingSerializer(booking).data,
            message="Reservation confirmed successfully.",
        )

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """
        Staff action: customer has picked up vehicle; rental is now ACTIVE.
        """
        booking = self.get_object()
        if booking.status not in [BookingStatus.CONFIRMED, BookingStatus.PENDING]:
            return self.error_response(
                message=f"Cannot activate booking with current status '{booking.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = BookingStatus.ACTIVE
        booking.save(update_fields=["status"])
        booking.vehicle.status = "rented"
        booking.vehicle.save(update_fields=["status"])

        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=getattr(request.user, "email", "concierge@tenant.local"),
            action="ACTIVATE_RENTAL",
            resource_type="Booking",
            resource_id=str(booking.id),
            details={"reference": booking.booking_reference, "vehicle": booking.vehicle.license_plate},
        )

        return self.success_response(
            data=BookingSerializer(booking).data,
            message="Rental contract activated. Vehicle marked as RENTED.",
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        Staff action: customer has returned vehicle; rental is COMPLETED.
        """
        booking = self.get_object()
        if booking.status != BookingStatus.ACTIVE:
            return self.error_response(
                message=f"Cannot complete booking that is not currently active (status: '{booking.status}').",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = BookingStatus.COMPLETED
        booking.save(update_fields=["status"])
        booking.vehicle.status = "available"
        booking.vehicle.save(update_fields=["status"])

        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=getattr(request.user, "email", "concierge@tenant.local"),
            action="COMPLETE_RENTAL",
            resource_type="Booking",
            resource_id=str(booking.id),
            details={"reference": booking.booking_reference, "vehicle": booking.vehicle.license_plate},
        )

        return self.success_response(
            data=BookingSerializer(booking).data,
            message="Rental marked as completed. Vehicle returned to fleet inventory.",
        )

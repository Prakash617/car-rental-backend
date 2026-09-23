from datetime import datetime

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.tenant.bookings.models import Booking, BookingAddon, BookingStatus
from apps.tenant.bookings.services.availability import AvailabilityService
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.pricing.services.calculator import PricingCalculatorService
from apps.tenant.vehicles.models import Vehicle


class BookingConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "BOOKING_UNAVAILABLE"
    default_detail = "The selected vehicle is no longer available for the specified dates."


class ReservationService:
    @classmethod
    def create_reservation(
        cls,
        vehicle_id: str,
        customer_data: dict,
        pickup_branch_id: str,
        return_branch_id: str,
        pickup_datetime: datetime,
        return_datetime: datetime,
        addon_ids: list[str] | None = None,
        coupon_code: str | None = None,
        notes: str | None = None,
    ) -> Booking:
        """
        Concurrency-safe, atomic reservation engine.
        Acquires a pessimistic row-level lock on the vehicle row to serialize
        concurrent checkout attempts and prevent double bookings.
        """
        if return_datetime <= pickup_datetime:
            raise APIException("Return date and time must be after pickup date and time.")

        with transaction.atomic():
            # 1. Acquire row-level lock on the vehicle record
            try:
                vehicle = Vehicle.objects.select_for_update().get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                raise APIException("Vehicle not found.") from None

            # 2. Re-verify availability inside locked transaction
            is_available = AvailabilityService.is_vehicle_available(
                vehicle_id=vehicle.id,
                pickup_datetime=pickup_datetime,
                return_datetime=return_datetime,
            )
            if not is_available:
                raise BookingConflictException()

            # 3. Resolve Branches
            pickup_branch = Branch.objects.get(id=pickup_branch_id)
            return_branch = Branch.objects.get(id=return_branch_id)

            # 4. Resolve or create Customer
            email = customer_data["email"].lower().strip()
            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": customer_data["first_name"],
                    "last_name": customer_data["last_name"],
                    "phone": customer_data["phone"],
                    "driver_license_number": customer_data["driver_license_number"],
                    "license_expiry_date": customer_data["license_expiry_date"],
                    "date_of_birth": customer_data["date_of_birth"],
                    "country": customer_data.get("country", "US"),
                },
            )

            # 5. Calculate Pricing Quote
            quote = PricingCalculatorService.calculate_quote(
                vehicle=vehicle,
                pickup_datetime=pickup_datetime,
                return_datetime=return_datetime,
                addon_ids=addon_ids,
                coupon_code=coupon_code,
            )

            # 6. Create Booking Record
            booking = Booking.objects.create(
                booking_reference=Booking.generate_booking_reference(),
                vehicle=vehicle,
                customer=customer,
                pickup_branch=pickup_branch,
                return_branch=return_branch,
                pickup_datetime=pickup_datetime,
                return_datetime=return_datetime,
                status=BookingStatus.PENDING,
                base_price=quote["base_price"],
                discount_amount=quote["discount_amount"],
                tax_amount=quote["tax_amount"],
                deposit_amount=quote["deposit_amount"],
                total_price=quote["total_price"],
                notes=notes,
            )

            # 7. Create Line Item Addons
            for addon_info in quote.get("addons", []):
                BookingAddon.objects.create(
                    booking=booking,
                    name=addon_info["name"],
                    price=addon_info["price"],
                    quantity=1,
                )

            return booking

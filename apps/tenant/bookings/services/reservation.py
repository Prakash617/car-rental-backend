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
        pickup_branch_id: str | None = None,
        return_branch_id: str | None = None,
        pickup_datetime: datetime | None = None,
        return_datetime: datetime | None = None,
        pickup_location: str = "",
        destination_location: str = "",
        stops: list[str] | None = None,
        trip_type: str = "return",
        decoration_name: str = "",
        decoration_price: float | int = 0,
        distance_km: float | int = 0,
        advance_amount: float | int = 0,
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

            # 3. Resolve Branches (optional)
            pickup_branch = None
            return_branch = None
            if pickup_branch_id:
                pickup_branch = Branch.objects.filter(id=pickup_branch_id).first()
            if return_branch_id:
                return_branch = Branch.objects.filter(id=return_branch_id).first()
            if not pickup_branch:
                pickup_branch = Branch.objects.first()
            if not return_branch:
                return_branch = pickup_branch

            # 4. Resolve or create Customer
            email = customer_data.get("email", "").lower().strip()
            first_name = customer_data.get("first_name", "")
            last_name = customer_data.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            phone = customer_data.get("phone", "")

            from datetime import date

            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "driver_license_number": customer_data.get("driver_license_number") or "SAJILO-CHAUFFEUR",
                    "license_expiry_date": customer_data.get("license_expiry_date") or date(2035, 1, 1),
                    "date_of_birth": customer_data.get("date_of_birth") or date(1995, 1, 1),
                    "country": customer_data.get("country", "NP"),
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

            dec_price = float(decoration_price or 0)
            total_calc_price = float(quote["total_price"]) + dec_price

            # 6. Create Booking Record
            booking = Booking.objects.create(
                booking_reference=Booking.generate_booking_reference(),
                vehicle=vehicle,
                customer=customer,
                pickup_branch=pickup_branch,
                return_branch=return_branch,
                pickup_datetime=pickup_datetime,
                return_datetime=return_datetime,
                pickup_location=pickup_location or (pickup_branch.name if pickup_branch else ""),
                destination_location=destination_location or (return_branch.name if return_branch else ""),
                stops=stops or [],
                trip_type=trip_type,
                decoration_name=decoration_name,
                decoration_price=dec_price,
                distance_km=float(distance_km or 0),
                customer_name=full_name,
                customer_phone=phone,
                customer_email=email,
                advance_amount=float(advance_amount or (total_calc_price * 0.10)),
                status=BookingStatus.PENDING,
                base_price=quote["base_price"],
                discount_amount=quote["discount_amount"],
                tax_amount=quote["tax_amount"],
                deposit_amount=quote["deposit_amount"],
                total_price=total_calc_price,
                notes=notes or "",
            )

            # 7. Create Line Item Addons
            for addon_info in quote.get("addons", []):
                BookingAddon.objects.create(
                    booking=booking,
                    name=addon_info["name"],
                    price=addon_info["price"],
                    quantity=1,
                )

        # 8. Dispatch notification & confirmation email
        try:
            from apps.tenant.notifications.services.notification_service import NotificationService
            NotificationService.dispatch_booking_confirmation(booking)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not dispatch confirmation email: {e}")

        return booking

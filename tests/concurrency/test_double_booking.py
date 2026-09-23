from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from apps.tenant.bookings.models import Booking
from apps.tenant.bookings.services.reservation import BookingConflictException, ReservationService
from apps.tenant.branches.models import Branch
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus


@pytest.fixture
def concurrency_branch(tenant_a):
    with schema_context(tenant_a.schema_name):
        branch = Branch.objects.filter(code="AP-01").first()
        if not branch:
            branch = Branch.objects.create(
                code="AP-01",
                name="Airport Terminal Hub",
                address_line1="Airport Way",
                city="Metropolis",
                postal_code="10002",
                country="US",
                phone="+1-555-0300",
                email="airport@alpha.com",
            )
        return branch


@pytest.fixture
def target_vehicle(tenant_a, concurrency_branch):
    with schema_context(tenant_a.schema_name):
        vehicle = Vehicle.objects.filter(license_plate="G-WAGON-01").first()
        if not vehicle:
            vehicle = Vehicle.objects.create(
                license_plate="G-WAGON-01",
                branch=concurrency_branch,
                brand="Mercedes-Benz",
                model="G 63 AMG",
                year=2024,
                category=VehicleCategory.LUXURY,
                daily_rate=Decimal("500.00"),
                deposit_amount=Decimal("1500.00"),
                status=VehicleStatus.AVAILABLE,
            )
        return vehicle


@pytest.mark.django_db(transaction=True)
class TestDoubleBookingConcurrency:
    def test_concurrent_reservations_serialized_without_double_booking(
        self, tenant_a, concurrency_branch, target_vehicle
    ):
        """
        Simulates two customers clicking 'Book Now' at the exact same millisecond
        for the same vehicle and conflicting dates.
        Pessimistic row-locking (select_for_update) inside transaction.atomic()
        must guarantee serialization:
        -> Exactly one customer gets 201 Created
        -> The other receives 409 Conflict (BookingConflictException)
        """
        # Clean up any existing bookings for this vehicle to guarantee fresh test state
        with schema_context(tenant_a.schema_name):
            Booking.objects.filter(vehicle=target_vehicle).delete()

        now = datetime.now(UTC)
        pickup = now + timedelta(days=5)
        return_dt = pickup + timedelta(days=4)

        customer_a_payload = {
            "first_name": "Bruce",
            "last_name": "Wayne",
            "email": "bruce@wayne-enterprises.com",
            "phone": "+1-555-1111",
            "driver_license_number": "DL-WAYNE-01",
            "license_expiry_date": now.date() + timedelta(days=500),
            "date_of_birth": now.date() - timedelta(days=12000),
        }

        customer_b_payload = {
            "first_name": "Clark",
            "last_name": "Kent",
            "email": "clark@daily-planet.com",
            "phone": "+1-555-2222",
            "driver_license_number": "DL-KENT-02",
            "license_expiry_date": now.date() + timedelta(days=500),
            "date_of_birth": now.date() - timedelta(days=11000),
        }

        results = []

        def attempt_booking(customer_data, thread_id):
            try:
                with schema_context(tenant_a.schema_name):
                    try:
                        booking = ReservationService.create_reservation(
                            vehicle_id=target_vehicle.id,
                            customer_data=customer_data,
                            pickup_branch_id=concurrency_branch.id,
                            return_branch_id=concurrency_branch.id,
                            pickup_datetime=pickup,
                            return_datetime=return_dt,
                            notes=f"Reserved via thread {thread_id}",
                        )
                        results.append(("SUCCESS", booking.booking_reference))
                    except BookingConflictException as e:
                        results.append(("CONFLICT", str(e)))
                    except Exception as e:
                        results.append(("ERROR", f"{type(e).__name__}: {str(e)}"))
            finally:
                from django.db import connections

                connections.close_all()

        # Launch concurrent threads simultaneously
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_booking, customer_a_payload, 1)
            f2 = executor.submit(attempt_booking, customer_b_payload, 2)
            f1.result()
            f2.result()

        successes = [r for r in results if r[0] == "SUCCESS"]
        conflicts = [r for r in results if r[0] == "CONFLICT"]
        errors = [r for r in results if r[0] == "ERROR"]

        assert len(errors) == 0, f"Unexpected errors during concurrent booking: {errors}"
        assert len(successes) == 1, (
            f"Expected exactly 1 booking to succeed, got {len(successes)}: {results}"
        )
        assert len(conflicts) == 1, (
            f"Expected exactly 1 booking to be rejected with conflict, got {len(conflicts)}: {results}"
        )

        # Verify database state in tenant schema
        with schema_context(tenant_a.schema_name):
            bookings = Booking.objects.filter(vehicle=target_vehicle)
            assert bookings.count() == 1, "Database must strictly contain exactly 1 booking record"
            assert bookings.first().booking_reference == successes[0][1]

        # Reset main connection to public for pytest-django teardown
        from django.db import connection, connections

        connections.close_all()
        connection.set_schema_to_public()

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from apps.tenant.bookings.models import Booking, BookingStatus
from apps.tenant.bookings.services.availability import AvailabilityService
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.maintenance.models import MaintenanceRecord, MaintenanceStatus
from apps.tenant.pricing.models import AddonPricingType, Coupon, DiscountType, ExtraAddon
from apps.tenant.pricing.services.calculator import PricingCalculatorService
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus


@pytest.fixture
def sample_branch(tenant_a):
    with schema_context(tenant_a.schema_name):
        return Branch.objects.create(
            name="Downtown Hub",
            code="DWTN",
            address_line1="100 Main Street",
            city="Metropolis",
            postal_code="10001",
            country="US",
            phone="+1-555-0100",
            email="dwtn@alpha.com",
        )


@pytest.fixture
def sample_vehicle(tenant_a, sample_branch):
    with schema_context(tenant_a.schema_name):
        return Vehicle.objects.create(
            branch=sample_branch,
            brand="Porsche",
            model="911 Carrera",
            year=2024,
            license_plate="POR-911",
            category=VehicleCategory.SPORTS,
            daily_rate=Decimal("350.00"),
            weekly_rate=Decimal("300.00"),
            monthly_rate=Decimal("250.00"),
            deposit_amount=Decimal("1000.00"),
            status=VehicleStatus.AVAILABLE,
        )


@pytest.mark.django_db
class TestRentalCoreAndIsolation:
    def test_cross_tenant_vehicle_isolation(self, api_client, tenant_a, tenant_b, sample_vehicle):
        """
        Vehicles belonging to Tenant A must NEVER be visible or accessible
        via Tenant B API or database.
        """
        # 1. Accessible via Tenant A
        resp_a = api_client.get(
            f"/api/v1/vehicles/{sample_vehicle.id}/", HTTP_HOST="alpha.platform.local"
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["data"]["license_plate"] == "POR-911"

        # 2. Querying the exact same ID under Tenant B domain returns 404
        resp_b = api_client.get(
            f"/api/v1/vehicles/{sample_vehicle.id}/", HTTP_HOST="beta.platform.local"
        )
        assert resp_b.status_code == 404
        assert resp_b.json()["error"]["code"] == "NOT_FOUND"

        # 3. Direct DB query in Tenant B schema yields None
        with schema_context(tenant_b.schema_name):
            assert not Vehicle.objects.filter(license_plate="POR-911").exists()

    def test_pricing_calculator_tiers_and_discounts(self, tenant_a, sample_vehicle):
        """
        Verifies dynamic price calculation across duration tiers,
        promotional coupons, and line item breakdowns.
        """
        with schema_context(tenant_a.schema_name):
            # Create Coupon: 10% off
            Coupon.objects.create(
                code="AUTUMN10",
                discount_type=DiscountType.PERCENTAGE,
                discount_value=Decimal("10.00"),
                min_rental_days=3,
            )
            # Create Add-on
            addon = ExtraAddon.objects.create(
                name="Full Coverage Insurance",
                price=Decimal("25.00"),
                pricing_type=AddonPricingType.PER_DAY,
            )

            now = datetime.now(UTC)
            # 7-day rental: should trigger weekly rate ($300/day instead of $350)
            pickup = now + timedelta(days=2)
            return_dt = pickup + timedelta(days=7)

            quote = PricingCalculatorService.calculate_quote(
                vehicle=sample_vehicle,
                pickup_datetime=pickup,
                return_datetime=return_dt,
                addon_ids=[str(addon.id)],
                coupon_code="AUTUMN10",
            )

            assert quote["billable_days"] == 7
            # Base price: 7 * $300 = $2100.00
            assert Decimal(quote["base_price"]) == Decimal("2100.00")
            # Discount: 10% of $2100 = $210.00
            assert Decimal(quote["discount_amount"]) == Decimal("210.00")
            # Add-on: 7 * $25 = $175.00
            assert len(quote["addons"]) == 1
            # Taxable subtotal: 2100 + 175 - 210 = 2065.00
            # Tax: 8% of 2065 = 165.20
            # Total: 2065 + 165.20 = 2230.20
            assert Decimal(quote["total_price"]) == Decimal("2230.20")
            assert Decimal(quote["deposit_amount"]) == Decimal("1000.00")

    def test_availability_service_blocks_overlapping_reservations(
        self, tenant_a, sample_vehicle, sample_branch
    ):
        """
        Verifies AvailabilityService properly marks a vehicle as unavailable
        when an active booking or maintenance window overlaps.
        """
        with schema_context(tenant_a.schema_name):
            now = datetime.now(UTC)
            pickup = now + timedelta(days=10)
            return_dt = pickup + timedelta(days=3)

            # Initially available
            assert (
                AvailabilityService.is_vehicle_available(sample_vehicle.id, pickup, return_dt)
                is True
            )

            # Create confirmed booking
            customer = Customer.objects.create(
                first_name="Diana",
                last_name="Prince",
                email="diana@alpha.com",
                phone="+1-555-0200",
                driver_license_number="DL-987654",
                license_expiry_date=now.date() + timedelta(days=365),
                date_of_birth=now.date() - timedelta(days=10000),
            )
            Booking.objects.create(
                booking_reference="BK-TEST-001",
                vehicle=sample_vehicle,
                customer=customer,
                pickup_branch=sample_branch,
                return_branch=sample_branch,
                pickup_datetime=pickup,
                return_datetime=return_dt,
                status=BookingStatus.CONFIRMED,
                base_price=Decimal("1000.00"),
                total_price=Decimal("1080.00"),
            )

            # Exact same window -> Unavailable
            assert (
                AvailabilityService.is_vehicle_available(sample_vehicle.id, pickup, return_dt)
                is False
            )
            # Overlapping start -> Unavailable
            assert (
                AvailabilityService.is_vehicle_available(
                    sample_vehicle.id, pickup - timedelta(days=1), pickup + timedelta(days=1)
                )
                is False
            )
            # Completely different window -> Available
            assert (
                AvailabilityService.is_vehicle_available(
                    sample_vehicle.id, return_dt + timedelta(days=5), return_dt + timedelta(days=8)
                )
                is True
            )

    def test_maintenance_blocks_vehicle_booking(self, tenant_a, sample_vehicle):
        """
        Verifies scheduled maintenance blocks availability.
        """
        with schema_context(tenant_a.schema_name):
            now = datetime.now(UTC)
            m_start = now + timedelta(days=20)
            m_end = m_start + timedelta(days=2)

            MaintenanceRecord.objects.create(
                vehicle=sample_vehicle,
                service_type="Major 30k Inspection",
                status=MaintenanceStatus.SCHEDULED,
                scheduled_start=m_start,
                scheduled_end=m_end,
            )

            # Booking during maintenance window is rejected
            assert (
                AvailabilityService.is_vehicle_available(sample_vehicle.id, m_start, m_end) is False
            )

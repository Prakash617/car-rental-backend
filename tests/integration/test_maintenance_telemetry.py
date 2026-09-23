from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from apps.platform.platform_users.models import PlatformUser
from apps.tenant.bookings.models import Booking, BookingStatus, PaymentStatus
from apps.tenant.bookings.services.availability import AvailabilityService
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.maintenance.models import (
    CleanlinessLevel,
    InspectionType,
    MaintenanceStatus,
    ServiceInterval,
    TelemetryRecord,
    TelemetrySource,
)
from apps.tenant.maintenance.services.maintenance_service import MaintenanceService
from apps.tenant.memberships.models import Membership, RoleChoices
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus


@pytest.fixture
def staff_inspector():
    return PlatformUser.objects.create_user(
        email="inspector_staff@alpha.com",
        first_name="Inspector",
        last_name="Gadget",
        password="ValidDevPassword123!",
    )


@pytest.fixture
def test_fleet_vehicle(tenant_a):
    with schema_context(tenant_a.schema_name):
        branch = Branch.objects.create(
            name="Main Garage Hub",
            code="GARAGE1",
            city="Kathmandu",
            country="NP",
            phone="+977-1-4222222",
            email="garage@alpha.com",
            address_line1="Ring Road 10",
        )
        return Vehicle.objects.create(
            branch=branch,
            brand="BMW",
            model="M5 Competition",
            year=2024,
            license_plate="M5-COMP-01",
            category=VehicleCategory.LUXURY,
            daily_rate=Decimal("450.00"),
            mileage=15000,
            status=VehicleStatus.AVAILABLE,
        )


@pytest.fixture
def active_booking(tenant_a, test_fleet_vehicle):
    with schema_context(tenant_a.schema_name):
        customer = Customer.objects.create(
            first_name="Tony",
            last_name="Stark",
            email="tony@stark.com",
            phone="+1-555-3000",
            driver_license_number="DL-NY-3000",
            license_expiry_date="2030-01-01",
            date_of_birth="1970-05-29",
            country="US",
        )
        now = datetime.now(tz=UTC)
        return Booking.objects.create(
            booking_reference="BK-FLEET01",
            vehicle=test_fleet_vehicle,
            customer=customer,
            pickup_branch=test_fleet_vehicle.branch,
            return_branch=test_fleet_vehicle.branch,
            pickup_datetime=now + timedelta(days=2),
            return_datetime=now + timedelta(days=5),
            base_price=Decimal("1350.00"),
            total_price=Decimal("1500.00"),
            status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID,
        )


@pytest.mark.django_db
class TestMaintenanceAndTelemetry:
    def test_schedule_maintenance_availability_blocking(self, tenant_a, test_fleet_vehicle):
        with schema_context(tenant_a.schema_name):
            now = datetime.now(tz=UTC)
            start = now + timedelta(days=10)
            end = now + timedelta(days=12)

            # Schedule maintenance
            record = MaintenanceService.schedule_maintenance(
                vehicle=test_fleet_vehicle,
                service_type="Brake Pad Replacement",
                scheduled_start=start,
                scheduled_end=end,
                service_center="BMW Official Workshop",
                notes="Inspect rotors as well",
            )

            assert record.status == MaintenanceStatus.SCHEDULED

            # Verify AvailabilityService blocks overlapping rental booking
            is_available = AvailabilityService.is_vehicle_available(
                vehicle_id=test_fleet_vehicle.id,
                pickup_datetime=start + timedelta(hours=1),
                return_datetime=end - timedelta(hours=1),
            )
            assert is_available is False, (
                "Vehicle must not be available during scheduled maintenance"
            )

    def test_schedule_maintenance_fails_if_booking_conflicts(
        self, tenant_a, test_fleet_vehicle, active_booking
    ):
        with schema_context(tenant_a.schema_name):
            # Attempt to schedule maintenance directly overlapping active_booking
            with pytest.raises(
                ValueError, match="not available during the requested maintenance window"
            ):
                MaintenanceService.schedule_maintenance(
                    vehicle=test_fleet_vehicle,
                    service_type="Transmission Service",
                    scheduled_start=active_booking.pickup_datetime + timedelta(hours=2),
                    scheduled_end=active_booking.return_datetime - timedelta(hours=2),
                )

    def test_start_and_complete_maintenance_lifecycle(self, tenant_a, test_fleet_vehicle):
        with schema_context(tenant_a.schema_name):
            now = datetime.now(tz=UTC)

            # Create interval rule
            interval = ServiceInterval.objects.create(
                vehicle=test_fleet_vehicle,
                service_name="Oil & Filter Service",
                interval_mileage=10000,
                last_service_mileage=10000,
            )

            record = MaintenanceService.schedule_maintenance(
                vehicle=test_fleet_vehicle,
                service_type="Oil & Filter Service",
                scheduled_start=now + timedelta(days=20),
                scheduled_end=now + timedelta(days=21),
            )

            # 1. Start maintenance
            started = MaintenanceService.start_maintenance(record.id)
            assert started.status == MaintenanceStatus.IN_PROGRESS

            test_fleet_vehicle.refresh_from_db()
            assert test_fleet_vehicle.status == VehicleStatus.MAINTENANCE

            # Verify telemetry logged
            telemetry1 = TelemetryRecord.objects.filter(
                vehicle=test_fleet_vehicle, source=TelemetrySource.SERVICE
            ).first()
            assert telemetry1 is not None

            # 2. Complete maintenance with higher odometer reading
            completed = MaintenanceService.complete_maintenance(
                record_id=record.id,
                odometer_reading=17500,
                cost=Decimal("380.00"),
                mechanic_notes="Replaced Castrol Edge 0W-30 and OEM filter.",
            )

            assert completed.status == MaintenanceStatus.COMPLETED
            assert completed.cost == Decimal("380.00")

            test_fleet_vehicle.refresh_from_db()
            assert test_fleet_vehicle.mileage == 17500
            assert test_fleet_vehicle.status == VehicleStatus.AVAILABLE

            # Verify ServiceInterval updated
            interval.refresh_from_db()
            assert interval.last_service_mileage == 17500
            assert interval.last_service_date == date.today()

    def test_checkout_inspection_updates_booking_and_vehicle(
        self, tenant_a, test_fleet_vehicle, active_booking, staff_inspector
    ):
        with schema_context(tenant_a.schema_name):
            # Pre-rental inspection at handover
            inspection = MaintenanceService.perform_inspection(
                vehicle=test_fleet_vehicle,
                inspection_type=InspectionType.CHECK_OUT,
                odometer=15050,
                fuel_percentage=100,
                booking=active_booking,
                inspector_id=staff_inspector.id,
                exterior_condition=CleanlinessLevel.EXCELLENT,
                interior_condition=CleanlinessLevel.EXCELLENT,
                customer_signature="sig_digital_token_999",
            )

            assert inspection.inspection_type == InspectionType.CHECK_OUT
            assert inspection.odometer == 15050

            # Vehicle is now RENTED
            test_fleet_vehicle.refresh_from_db()
            assert test_fleet_vehicle.status == VehicleStatus.RENTED
            assert test_fleet_vehicle.mileage == 15050

            # Booking is now ACTIVE
            active_booking.refresh_from_db()
            assert active_booking.status == BookingStatus.ACTIVE

            # Telemetry stream entry created
            telemetry = TelemetryRecord.objects.get(
                vehicle=test_fleet_vehicle, source=TelemetrySource.TRIP_CHECKOUT
            )
            assert telemetry.odometer == 15050

    def test_checkin_inspection_with_damage_flags_vehicle(
        self, tenant_a, test_fleet_vehicle, active_booking, staff_inspector
    ):
        with schema_context(tenant_a.schema_name):
            # Check-out first
            MaintenanceService.perform_inspection(
                vehicle=test_fleet_vehicle,
                inspection_type=InspectionType.CHECK_OUT,
                odometer=15000,
                fuel_percentage=100,
                booking=active_booking,
                inspector_id=staff_inspector.id,
            )

            # Customer returns car with bumper scratch and 500 km traveled
            inspection = MaintenanceService.perform_inspection(
                vehicle=test_fleet_vehicle,
                inspection_type=InspectionType.CHECK_IN,
                odometer=15500,
                fuel_percentage=75,
                booking=active_booking,
                inspector_id=staff_inspector.id,
                has_new_damage=True,
                damage_description="Deep scratch on rear passenger bumper",
                damage_photos=["https://s3.amazonaws.com/damages/photo1.jpg"],
            )

            assert inspection.has_new_damage is True

            # Booking completed with damage notice in notes
            active_booking.refresh_from_db()
            assert active_booking.status == BookingStatus.COMPLETED
            assert "DAMAGE DETECTED" in active_booking.notes

            # Vehicle status routed to MAINTENANCE for repair assessment
            test_fleet_vehicle.refresh_from_db()
            assert test_fleet_vehicle.status == VehicleStatus.MAINTENANCE
            assert test_fleet_vehicle.mileage == 15500

    def test_fleet_health_overview_api(
        self, tenant_a, test_fleet_vehicle, staff_inspector, api_client
    ):
        with schema_context(tenant_a.schema_name):
            Membership.objects.create(
                user_id=staff_inspector.id,
                role=RoleChoices.MANAGER,
                is_active=True,
            )

            api_client.force_authenticate(user=staff_inspector)
            resp = api_client.get("/api/v1/maintenance/overview/", HTTP_HOST="alpha.platform.local")

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "fleet_size" in data
            assert "available" in data
            assert "in_maintenance" in data
            assert data["fleet_size"] >= 1

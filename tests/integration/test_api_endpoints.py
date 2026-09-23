from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIClient

from apps.platform.platform_users.models import PlatformUser
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.memberships.models import Membership, RoleChoices
from apps.tenant.pricing.models import ExtraAddon
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from apps.tenant.websites.models import WebsiteConfig


@pytest.fixture
def tenant_staff_user(db):
    return PlatformUser.objects.create_user(
        email="staff.alpha@platform.com",
        password="SecureStaffPass123!",
        first_name="Alice",
        last_name="Staff",
    )


@pytest.fixture
def tenant_admin_user(db):
    return PlatformUser.objects.create_user(
        email="admin.alpha@platform.com",
        password="SecureAdminPass123!",
        first_name="Bob",
        last_name="Admin",
    )


@pytest.fixture
def setup_api_data(tenant_a, tenant_staff_user, tenant_admin_user):
    with schema_context(tenant_a.schema_name):
        Membership.objects.create(
            user_id=tenant_staff_user.id,
            role=RoleChoices.STAFF,
            is_active=True,
        )
        Membership.objects.create(
            user_id=tenant_admin_user.id,
            role=RoleChoices.ADMIN,
            is_active=True,
        )

        branch = Branch.objects.create(
            name="Alpha Airport Concierge",
            code="ALP-AIR",
            city="Kathmandu",
            country="NP",
            phone="+977-1-4444444",
            email="concierge@alpha-rentals.com",
            is_active=True,
        )

        vehicle_active = Vehicle.objects.create(
            branch=branch,
            brand="Porsche",
            model="911 Carrera S",
            year=2024,
            license_plate="LUX-911",
            category=VehicleCategory.SPORTS,
            daily_rate=Decimal("450.00"),
            deposit_amount=Decimal("1500.00"),
            status=VehicleStatus.AVAILABLE,
        )

        vehicle_inactive = Vehicle.objects.create(
            branch=branch,
            brand="Old",
            model="Decommissioned",
            year=2015,
            license_plate="OLD-000",
            category=VehicleCategory.ECONOMY,
            daily_rate=Decimal("50.00"),
            deposit_amount=Decimal("200.00"),
            status=VehicleStatus.INACTIVE,
        )

        customer = Customer.objects.create(
            first_name="Bruce",
            last_name="Wayne",
            email="bruce@wayne-enterprises.com",
            phone="+1-555-0199",
            driver_license_number="DL-GOTHAM-001",
            license_expiry_date="2032-12-31",
            date_of_birth="1985-05-19",
            country="US",
            is_verified=True,
        )

        addon = ExtraAddon.objects.create(
            name="GPS Navigation & Telemetry",
            price=Decimal("15.00"),
            pricing_type="per_day",
            is_active=True,
        )

        WebsiteConfig.objects.create(
            active_theme="luxury",
            primary_color="#D4AF37",
            accent_color="#B38F26",
            support_email="concierge@alpha-rentals.com",
            support_phone="+977-1-4444444",
        )

        return {
            "branch": branch,
            "vehicle": vehicle_active,
            "inactive_vehicle": vehicle_inactive,
            "customer": customer,
            "addon": addon,
        }


@pytest.mark.django_db
class TestPublicRentalEndpoints:
    def test_public_website_config_endpoint(self, tenant_a, setup_api_data):
        client = APIClient()
        response = client.get("/api/v1/website/config/", HTTP_HOST="alpha.platform.local")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["active_theme"] == "luxury"
        assert data["data"]["primary_color"] == "#D4AF37"
        assert data["data"]["support_email"] == "concierge@alpha-rentals.com"

    def test_public_branch_catalog(self, tenant_a, setup_api_data):
        client = APIClient()
        response = client.get("/api/v1/branches/", HTTP_HOST="alpha.platform.local")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) >= 1
        assert any(b["code"] == "ALP-AIR" for b in data["data"])

    def test_public_vehicle_catalog_filters_inactive(self, tenant_a, setup_api_data):
        client = APIClient()
        response = client.get("/api/v1/vehicles/", HTTP_HOST="alpha.platform.local")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Inactive vehicles must never be exposed publicly
        plates = [v["license_plate"] for v in data["data"]]
        assert "LUX-911" in plates
        assert "OLD-000" not in plates

    def test_pricing_quote_calculation(self, tenant_a, setup_api_data):
        client = APIClient()
        vehicle = setup_api_data["vehicle"]
        addon = setup_api_data["addon"]

        now = datetime.now(tz=UTC)
        payload = {
            "vehicle_id": str(vehicle.id),
            "pickup_datetime": (now + timedelta(days=2)).isoformat(),
            "return_datetime": (now + timedelta(days=5)).isoformat(),
            "addon_ids": [str(addon.id)],
        }

        response = client.post(
            "/api/v1/pricing/quote/",
            data=payload,
            format="json",
            HTTP_HOST="alpha.platform.local",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        quote = data["data"]
        assert quote["billable_days"] == 3
        assert Decimal(quote["base_price"]) == Decimal("1350.00")
        assert len(quote["addons"]) == 1
        assert Decimal(quote["total_price"]) > Decimal("1350.00")  # includes addons and tax

    def test_public_booking_checkout_and_lookup(self, tenant_a, setup_api_data):
        client = APIClient()
        vehicle = setup_api_data["vehicle"]
        branch = setup_api_data["branch"]

        now = datetime.now(tz=UTC)
        checkout_payload = {
            "vehicle_id": str(vehicle.id),
            "pickup_branch_id": str(branch.id),
            "return_branch_id": str(branch.id),
            "pickup_datetime": (now + timedelta(days=10)).isoformat(),
            "return_datetime": (now + timedelta(days=14)).isoformat(),
            "customer": {
                "first_name": "Tony",
                "last_name": "Stark",
                "email": "tony@stark.com",
                "phone": "+1-555-0100",
                "driver_license_number": "DL-CA-9988",
                "license_expiry_date": "2030-01-01",
                "date_of_birth": "1970-05-29",
                "country": "US",
            },
            "notes": "VIP airport ramp delivery requested",
        }

        # 1. Create booking
        response = client.post(
            "/api/v1/bookings/",
            data=checkout_payload,
            format="json",
            HTTP_HOST="alpha.platform.local",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = response.json()["data"]
        ref = created["booking_reference"]
        booking_id = created["id"]
        assert ref.startswith("BK-")

        # 2. Public lookup by reference
        lookup_res = client.get(
            f"/api/v1/bookings/lookup/{ref}/",
            HTTP_HOST="alpha.platform.local",
        )
        assert lookup_res.status_code == status.HTTP_200_OK
        assert lookup_res.json()["data"]["booking_reference"] == ref

        # 3. Cancel booking
        cancel_res = client.post(
            f"/api/v1/bookings/{booking_id}/cancel/",
            HTTP_HOST="alpha.platform.local",
        )
        assert cancel_res.status_code == status.HTTP_200_OK
        assert cancel_res.json()["data"]["status"] == "cancelled"


@pytest.mark.django_db
class TestProtectedDashboardEndpoints:
    def test_anonymous_access_blocked_on_protected_endpoints(self, tenant_a):
        client = APIClient()
        # Customer CRM is protected
        res = client.get("/api/v1/customers/", HTTP_HOST="alpha.platform.local")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # Dashboard overview is protected
        res = client.get("/api/v1/dashboard/overview/", HTTP_HOST="alpha.platform.local")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_overview_metrics_for_staff(
        self, tenant_a, tenant_staff_user, setup_api_data
    ):
        client = APIClient()
        client.force_authenticate(user=tenant_staff_user)

        response = client.get(
            "/api/v1/dashboard/overview/",
            HTTP_HOST="alpha.platform.local",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        overview = data["data"]
        assert "fleet_total" in overview
        assert "fleet_utilization_rate" in overview
        assert "bookings_active" in overview
        assert "revenue_this_month" in overview

    def test_theme_customization_by_admin(self, tenant_a, tenant_admin_user, setup_api_data):
        client = APIClient()
        client.force_authenticate(user=tenant_admin_user)

        # Update theme to modern with cobalt accent
        patch_res = client.patch(
            "/api/v1/dashboard/theme/",
            data={
                "active_theme": "modern",
                "primary_color": "#2563EB",
                "hero_title": "Rent on Demand. Drive the Future.",
            },
            format="json",
            HTTP_HOST="alpha.platform.local",
        )

        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.json()["data"]["active_theme"] == "modern"
        assert patch_res.json()["data"]["primary_color"] == "#2563EB"

        # Verify next public request immediately reflects the update
        anon_client = APIClient()
        public_res = anon_client.get(
            "/api/v1/website/config/",
            HTTP_HOST="alpha.platform.local",
        )
        assert public_res.status_code == status.HTTP_200_OK
        assert public_res.json()["data"]["active_theme"] == "modern"
        assert public_res.json()["data"]["primary_color"] == "#2563EB"

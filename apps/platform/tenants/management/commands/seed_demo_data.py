from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from apps.platform.domains.models import Domain
from apps.platform.platform_users.models import PlatformUser
from apps.platform.tenants.models import Tenant
from apps.tenant.bookings.models import Booking, BookingStatus, PaymentStatus
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.memberships.models import Membership, RoleChoices
from apps.tenant.pricing.models import (
    AddonPricingType,
    Coupon,
    DiscountType,
    ExtraAddon,
    SeasonalRate,
)
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from apps.tenant.websites.models import ThemeChoice, WebsiteConfig


class Command(BaseCommand):
    help = "Seeds real demo data for testing the multi-tenant Car Rental SaaS MVP."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("===> Starting SaaS demo data seeding..."))

        # 1. Public Schema Tenant
        public_tenant, created = Tenant.objects.get_or_create(
            schema_name="public",
            defaults={
                "name": "Platform Administration",
                "slug": "platform-admin",
                "is_active": True,
            },
        )
        Domain.objects.get_or_create(
            domain="platform.local",
            defaults={"tenant": public_tenant, "is_primary": True, "is_verified": True},
        )

        # 2. Platform Superuser
        admin_user, created = PlatformUser.objects.get_or_create(
            email="admin@platform.com",
            defaults={
                "first_name": "Alexander",
                "last_name": "Pierce",
                "is_platform_admin": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123456")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created platform admin: admin@platform.com / admin123456"))

        # 3. Demo Tenant: Apex Luxury Concierge
        tenant_apex, created = Tenant.objects.get_or_create(
            schema_name="tenant_apex",
            defaults={
                "name": "Apex Luxury Concierge",
                "slug": "apex-luxury",
                "is_active": True,
                "timezone": "UTC",
                "currency": "USD",
            },
        )

        # Bind local development domains to Apex tenant for immediate access
        for domain_name, is_primary in [("localhost", True), ("127.0.0.1", False), ("apex.localhost", False)]:
            Domain.objects.get_or_create(
                domain=domain_name,
                defaults={"tenant": tenant_apex, "is_primary": is_primary, "is_verified": True},
            )

        self.stdout.write(self.style.SUCCESS(f"Provisioned tenant schema: {tenant_apex.schema_name}"))

        # 4. Populate Tenant Schema Data
        with schema_context(tenant_apex.schema_name):
            # Admin Membership
            Membership.objects.get_or_create(
                user_id=admin_user.id,
                defaults={"role": RoleChoices.OWNER, "is_active": True},
            )

            # Concierge Staff User
            staff_user, s_created = PlatformUser.objects.get_or_create(
                email="concierge@apex-fleet.com",
                defaults={
                    "first_name": "Julian",
                    "last_name": "Vane",
                    "is_platform_admin": False,
                },
            )
            if s_created:
                staff_user.set_password("concierge123")
                staff_user.save()

            Membership.objects.get_or_create(
                user_id=staff_user.id,
                defaults={"role": RoleChoices.STAFF, "is_active": True},
            )

            # Website Branding & Theme
            config, _ = WebsiteConfig.objects.get_or_create(
                defaults={
                    "active_theme": ThemeChoice.LUXURY,
                    "primary_color": "#D4AF37",
                    "accent_color": "#B38F26",
                    "font_heading": "serif",
                    "support_email": "concierge@apex-fleet.com",
                    "support_phone": "+1 (800) 555-APEX",
                    "hero_title": "The Pinnacle of Automotive Luxury",
                    "hero_subtitle": "Experience peerless performance and white-glove concierge mobility.",
                    "seo_meta_title": "Apex Luxury Concierge | Exotic & Luxury Automobile Hire",
                    "seo_meta_description": "Curated exotic fleet, private tarmac delivery, and 24/7 dedicated concierge service.",
                }
            )

            # Branches
            hub_branch, _ = Branch.objects.get_or_create(
                code="HUB-DT",
                defaults={
                    "name": "Downtown Concierge Hub",
                    "city": "Kathmandu",
                    "country": "NP",
                    "phone": "+977-1-4441000",
                    "email": "downtown@apex-fleet.com",
                    "is_active": True,
                },
            )

            airport_branch, _ = Branch.objects.get_or_create(
                code="VIP-AIR",
                defaults={
                    "name": "Airport VIP Terminal",
                    "city": "Kathmandu",
                    "country": "NP",
                    "phone": "+977-1-4442000",
                    "email": "airport@apex-fleet.com",
                    "is_active": True,
                },
            )

            # Fleet Vehicles
            vehicles_data = [
                {
                    "brand": "Porsche",
                    "model": "911 GT3 RS",
                    "year": 2024,
                    "license_plate": "LUX-911",
                    "category": VehicleCategory.SPORTS,
                    "transmission": "automatic",
                    "fuel_type": "petrol",
                    "seats": 2,
                    "doors": 2,
                    "mileage": 3200,
                    "color": "Shark Blue",
                    "status": VehicleStatus.AVAILABLE,
                    "daily_rate": Decimal("890.00"),
                    "deposit_amount": Decimal("2500.00"),
                    "images": [{"url": "https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
                    "features": ["4.0L Naturally Aspirated Boxer-6", "Carbon Ceramic Brakes", "Front Axle Lift"],
                    "description": "518 hp high-revving track masterpiece.",
                    "branch": hub_branch,
                },
                {
                    "brand": "Land Rover",
                    "model": "Range Rover SV Autobiography",
                    "year": 2024,
                    "license_plate": "SV-440",
                    "category": VehicleCategory.LUXURY,
                    "transmission": "automatic",
                    "fuel_type": "hybrid",
                    "seats": 5,
                    "doors": 4,
                    "mileage": 6400,
                    "color": "Belgravia Green",
                    "status": VehicleStatus.AVAILABLE,
                    "daily_rate": Decimal("750.00"),
                    "deposit_amount": Decimal("2000.00"),
                    "images": [{"url": "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
                    "features": ["Executive Rear Seating with Massage", "Meridian Signature 1600W", "Adaptive Air Suspension"],
                    "description": "The quintessential luxury flagship SUV.",
                    "branch": airport_branch,
                },
                {
                    "brand": "Tesla",
                    "model": "Model S Plaid",
                    "year": 2024,
                    "license_plate": "EV-1020",
                    "category": VehicleCategory.ELECTRIC,
                    "transmission": "automatic",
                    "fuel_type": "electric",
                    "seats": 5,
                    "doors": 4,
                    "mileage": 5100,
                    "color": "Solid Black",
                    "status": VehicleStatus.AVAILABLE,
                    "daily_rate": Decimal("490.00"),
                    "deposit_amount": Decimal("1500.00"),
                    "images": [{"url": "https://images.unsplash.com/photo-1617788138017-80ad40651399?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
                    "features": ["1,020 HP Tri-Motor", "0-60 mph in 1.99s", "Free Supercharging Included"],
                    "description": "Blistering EV acceleration with autonomous capability.",
                    "branch": hub_branch,
                },
                {
                    "brand": "Mercedes-AMG",
                    "model": "G 63 Biturbo",
                    "year": 2024,
                    "license_plate": "AMG-630",
                    "category": VehicleCategory.SUV,
                    "transmission": "automatic",
                    "fuel_type": "petrol",
                    "seats": 5,
                    "doors": 5,
                    "mileage": 8200,
                    "color": "Designo Night Black Magno",
                    "status": VehicleStatus.AVAILABLE,
                    "daily_rate": Decimal("950.00"),
                    "deposit_amount": Decimal("3000.00"),
                    "images": [{"url": "https://images.unsplash.com/photo-1520031441872-265e4ff70366?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
                    "features": ["Handcrafted 577 HP V8", "AMG Side-Exit Exhaust", "Triple Locking Diffs"],
                    "description": "Iconic military-grade design with high-octane luxury.",
                    "branch": airport_branch,
                },
                {
                    "brand": "BMW",
                    "model": "i7 xDrive60 Excellence",
                    "year": 2024,
                    "license_plate": "VIP-007",
                    "category": VehicleCategory.LUXURY,
                    "transmission": "automatic",
                    "fuel_type": "electric",
                    "seats": 5,
                    "doors": 4,
                    "mileage": 4300,
                    "color": "Oxide Grey Metallic",
                    "status": VehicleStatus.AVAILABLE,
                    "daily_rate": Decimal("680.00"),
                    "deposit_amount": Decimal("1800.00"),
                    "images": [{"url": "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
                    "features": ["31.3-inch 8K Theatre Screen", "Bowers & Wilkins 4D Sound", "Crystal Headlights"],
                    "description": "Private cinema rear lounge with whisper-quiet electric drive.",
                    "branch": hub_branch,
                },
            ]

            for v_data in vehicles_data:
                branch = v_data.pop("branch")
                plate = v_data["license_plate"]
                Vehicle.objects.update_or_create(
                    license_plate=plate,
                    defaults={**v_data, "branch": branch},
                )

            # Addons
            ExtraAddon.objects.get_or_create(
                name="Dedicated Chauffeur Service",
                defaults={"price": Decimal("250.00"), "pricing_type": AddonPricingType.PER_DAY, "is_active": True},
            )
            ExtraAddon.objects.get_or_create(
                name="Tarmac VIP Helicopter Transfer",
                defaults={"price": Decimal("850.00"), "pricing_type": AddonPricingType.PER_RENTAL, "is_active": True},
            )
            ExtraAddon.objects.get_or_create(
                name="Zero-Excess Comprehensive Damage Shield",
                defaults={"price": Decimal("75.00"), "pricing_type": AddonPricingType.PER_DAY, "is_active": True},
            )

            # Coupons
            Coupon.objects.get_or_create(
                code="CONCIERGE10",
                defaults={
                    "discount_type": DiscountType.PERCENTAGE,
                    "discount_value": Decimal("10.00"),
                    "min_rental_days": 2,
                    "is_active": True,
                },
            )

            # Demo Customer & Booking
            customer, _ = Customer.objects.get_or_create(
                email="bruce@wayne-enterprises.com",
                defaults={
                    "first_name": "Bruce",
                    "last_name": "Wayne",
                    "phone": "+1 (555) 019-9000",
                    "driver_license_number": "DL-GOTHAM-001",
                    "license_expiry_date": "2032-12-31",
                    "date_of_birth": "1985-05-19",
                    "country": "US",
                    "is_verified": True,
                },
            )

            porsche = Vehicle.objects.get(license_plate="LUX-911")
            now = datetime.now(tz=UTC)
            Booking.objects.get_or_create(
                booking_reference="BK-APEX-8801",
                defaults={
                    "vehicle": porsche,
                    "customer": customer,
                    "pickup_branch": hub_branch,
                    "return_branch": airport_branch,
                    "pickup_datetime": now + timedelta(days=1),
                    "return_datetime": now + timedelta(days=4),
                    "status": BookingStatus.CONFIRMED,
                    "base_price": Decimal("2670.00"),
                    "total_price": Decimal("2883.60"),
                    "payment_status": PaymentStatus.PAID,
                    "deposit_amount": Decimal("2500.00"),
                    "notes": "VIP Client. Deliver vehicle directly to private hangar 4.",
                },
            )

        self.stdout.write(self.style.SUCCESS("===> Seed data successfully generated for Apex Luxury Concierge!"))

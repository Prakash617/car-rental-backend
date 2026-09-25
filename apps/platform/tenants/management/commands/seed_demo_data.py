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
from apps.tenant.websites.models import CustomPage, FAQ, ThemeChoice, WebsiteConfig


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

            # Storefront FAQs
            faqs = [
                {"question": "What documents do I need to rent a vehicle?", "answer": "You will need a valid driver's license, a major credit card in your name, and a government-issued photo ID. International guests must also present their passport.", "order": 0},
                {"question": "What is your fuel policy?", "answer": "Our vehicles are provided with a full tank. We ask that you return the vehicle with a full tank of fuel. If returned with less fuel, a refueling charge will apply based on current market rates plus a service fee.", "order": 1},
                {"question": "Can I add an additional driver?", "answer": "Yes. Additional drivers can be added at the time of rental. Each additional driver must be present at pickup with a valid license and must meet our standard driver eligibility requirements.", "order": 2},
                {"question": "What is your cancellation policy?", "answer": "Reservations cancelled 48 hours or more before pickup receive a full refund. Cancellations within 24–48 hours incur a 25% fee. Cancellations within 24 hours are non-refundable.", "order": 3},
                {"question": "Is there a security deposit?", "answer": "A security deposit is held on your credit card at the time of pickup. The amount varies by vehicle category. Deposits are fully released within 5–7 business days after vehicle return, provided there is no damage.", "order": 4},
                {"question": "Do you offer airport pickup?", "answer": "Yes. We offer complimentary airport delivery and collection for all premium and elite vehicle categories. Standard category vehicles can be delivered for an additional fee. Please arrange this 24 hours in advance.", "order": 5},
                {"question": "What happens if I return the vehicle late?", "answer": "A grace period of 60 minutes is provided at no charge. After that, an additional half-day rental rate is charged for each hour beyond the grace period.", "order": 6},
                {"question": "Are your vehicles GPS-equipped?", "answer": "All our vehicles come equipped with built-in satellite navigation systems. Additional portable GPS units are available upon request. Our fleet also supports Apple CarPlay and Android Auto.", "order": 7},
            ]
            for faq_data in faqs:
                FAQ.objects.get_or_create(question=faq_data["question"], defaults=faq_data)

            # Custom Pages
            pages = [
                {
                    "title": "Terms & Conditions",
                    "slug": "terms-and-conditions",
                    "content": "# Terms & Conditions\n\n**Effective Date:** January 1, 2025\n\n## 1. Rental Agreement\nBy completing a reservation with Apex Luxury Concierge, you agree to be bound by these terms and conditions in their entirety.\n\n## 2. Driver Eligibility\nAll primary drivers must be 25 years of age or older, hold a valid full driving license for a minimum of 2 years, and present a valid credit card at the time of collection.\n\n## 3. Insurance & Liability\nOur vehicles are covered by comprehensive insurance. Our Collision Damage Waiver (CDW) reduces your financial liability in the event of an accident. Full liability remains with the renter until CDW is purchased.\n\n## 4. Damage & Condition\nVehicles must be returned in the same condition as collected. Any damage, soiling, or unusual wear will be assessed and charged accordingly.\n\n## 5. Fuel Policy\nAll vehicles are provided and must be returned with a full tank of fuel. Failure to do so will result in a refueling service charge.\n\n## 6. Prohibited Use\nVehicles may not be used for racing, off-road driving (unless specified), sub-letting, or transportation of illegal materials.\n\n## 7. Cancellation Policy\nPlease refer to our dedicated Cancellation Policy section for full details on refund timelines and applicable fees.\n\n## 8. Governing Law\nThese terms are governed by the laws of the jurisdiction in which the rental takes place.\n",
                    "is_published": True,
                    "seo_title": "Terms & Conditions — Apex Luxury Concierge",
                    "seo_description": "Read the full terms and conditions for renting vehicles from Apex Luxury Concierge.",
                },
                {
                    "title": "Privacy Policy",
                    "slug": "privacy-policy",
                    "content": "# Privacy Policy\n\n**Last Updated:** January 1, 2025\n\n## What We Collect\nWe collect personal information you provide when making a reservation, including name, email address, phone number, driver's license details, and payment information.\n\n## How We Use Your Data\nYour data is used to process reservations, communicate booking confirmations, and improve our services. We do not sell your data to third parties.\n\n## Data Security\nAll personal information is stored securely using industry-standard encryption. Payment data is handled by PCI-DSS compliant processors.\n\n## Your Rights\nYou have the right to access, correct, or request deletion of your personal data at any time. Contact us at privacy@apex-fleet.com.\n\n## Cookies\nWe use essential cookies to maintain your session and preferences. Analytics cookies help us improve the booking experience.\n",
                    "is_published": True,
                    "seo_title": "Privacy Policy — Apex Luxury Concierge",
                    "seo_description": "Learn how Apex Luxury Concierge collects and protects your personal data.",
                },
                {
                    "title": "About Us",
                    "slug": "about",
                    "content": "# About Apex Luxury Concierge\n\n## Our Story\nFounded with a singular vision — to redefine what premium vehicle rental means — Apex Luxury Concierge is the choice of discerning travellers, executives, and enthusiasts who demand the finest.\n\n## Our Fleet\nWe curate an exclusive selection of the world's most prestigious vehicles. From the commanding presence of a Range Rover Autobiography to the effortless performance of a Porsche Panamera, every car in our fleet is maintained to the highest standards.\n\n## Our Promise\n- **White-glove delivery** — your vehicle, at your location, on your schedule\n- **Concierge service** — a dedicated specialist available 24/7\n- **Zero-compromise maintenance** — every vehicle inspected before every rental\n- **Transparent pricing** — no hidden charges, no surprises\n\n## Contact Us\n📧 concierge@apex-fleet.com  \n📞 +1 (800) 555-APEX  \n🕐 Available 24 hours, 7 days a week\n",
                    "is_published": True,
                    "seo_title": "About Apex Luxury Concierge — Premium Vehicle Rental",
                    "seo_description": "Learn about Apex Luxury Concierge and our commitment to premium automotive experiences.",
                },
            ]
            for page_data in pages:
                CustomPage.objects.get_or_create(slug=page_data["slug"], defaults=page_data)

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
                    "images": [{"url": "https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?auto=format&fit=crop&w=1200&q=80", "is_primary": True}],
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

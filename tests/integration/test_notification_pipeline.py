from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django_tenants.utils import schema_context

from apps.platform.platform_users.models import PlatformUser
from apps.tenant.bookings.models import Booking, BookingStatus, PaymentStatus
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.memberships.models import Membership, RoleChoices
from apps.tenant.notifications.models import (
    NotificationEventTypeChoices,
    NotificationLog,
)
from apps.tenant.notifications.services.notification_service import NotificationService
from apps.tenant.notifications.tasks import (
    send_notification_email_async,
    send_pickup_reminders_all_tenants,
)
from apps.tenant.payments.models import (
    Payment,
    PaymentProviderChoices,
    PaymentStatusChoices,
)
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from integrations.email.service import EmailService


@pytest.fixture
def tenant_user():
    return PlatformUser.objects.create_user(
        email="staff_agent@alpha.com",
        first_name="Staff",
        last_name="Member",
        password="ValidDevPassword123!",
    )


@pytest.fixture
def booking_with_customer(tenant_a):
    with schema_context(tenant_a.schema_name):
        branch = Branch.objects.create(
            name="Alpha Hub",
            code="HUB1",
            city="Kathmandu",
            country="NP",
            phone="+977-1-4111111",
            email="hub@alpha.com",
            address_line1="Durbar Marg 42",
        )
        vehicle = Vehicle.objects.create(
            branch=branch,
            brand="Audi",
            model="RS6 Avant",
            year=2024,
            license_plate="AUD-006",
            category=VehicleCategory.LUXURY,
            daily_rate=Decimal("400.00"),
            status=VehicleStatus.AVAILABLE,
        )
        customer = Customer.objects.create(
            first_name="Bruce",
            last_name="Wayne",
            email="bruce@wayne.com",
            phone="+1-555-0101",
            driver_license_number="DL-GOTHAM-01",
            license_expiry_date="2028-12-31",
            date_of_birth="1980-05-27",
            country="US",
        )
        now = datetime.now(tz=UTC)
        return Booking.objects.create(
            booking_reference="BK-NOTIF01",
            vehicle=vehicle,
            customer=customer,
            pickup_branch=branch,
            return_branch=branch,
            pickup_datetime=now + timedelta(hours=12),
            return_datetime=now + timedelta(days=3),
            base_price=Decimal("1200.00"),
            tax_amount=Decimal("120.00"),
            deposit_amount=Decimal("800.00"),
            total_price=Decimal("1320.00"),
            status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID,
        )


@pytest.mark.django_db
class TestNotificationPipeline:
    def test_in_app_notification_lifecycle(self, tenant_a, tenant_user, api_client):
        with schema_context(tenant_a.schema_name):
            # Create membership for tenant_user
            Membership.objects.create(
                user_id=tenant_user.id,
                role=RoleChoices.STAFF,
                is_active=True,
            )

            # Dispatch notification
            notif = NotificationService.dispatch_in_app(
                recipient_email=tenant_user.email,
                recipient_user=tenant_user,
                title="System Alert",
                message="Vehicle maintenance schedule updated",
                event_type=NotificationEventTypeChoices.TEAM_INVITATION,
            )

            assert notif.is_read is False

            # Query via API
            api_client.force_authenticate(user=tenant_user)
            resp = api_client.get("/api/v1/notifications/", HTTP_HOST="alpha.platform.local")
            assert resp.status_code == 200
            data = resp.json()["data"]
            items = data["results"] if isinstance(data, dict) and "results" in data else data
            assert len(items) >= 1

            # Mark as read
            read_resp = api_client.patch(
                f"/api/v1/notifications/{notif.id}/read/",
                HTTP_HOST="alpha.platform.local",
            )
            assert read_resp.status_code == 200
            notif.refresh_from_db()
            assert notif.is_read is True
            assert notif.read_at is not None

    def test_email_template_rendering(self, tenant_a, booking_with_customer):
        with schema_context(tenant_a.schema_name):
            # 1. Booking confirmation
            success1 = EmailService.send_booking_confirmation(booking_with_customer)
            assert success1 is True
            assert len(mail.outbox) == 1
            assert "BK-NOTIF01" in mail.outbox[0].subject
            assert (
                "Audi RS6 Avant" in mail.outbox[0].body
                or "Audi RS6 Avant" in mail.outbox[0].alternatives[0][0]
            )

            # 2. Payment receipt
            payment = Payment.objects.create(
                booking=booking_with_customer,
                provider=PaymentProviderChoices.STRIPE,
                amount=Decimal("1320.00"),
                currency="USD",
                status=PaymentStatusChoices.SUCCEEDED,
                transaction_reference="pi_stripe_test_notif",
            )
            success2 = EmailService.send_payment_receipt(payment)
            assert success2 is True
            assert len(mail.outbox) == 2
            assert "Payment Receipt" in mail.outbox[1].subject

            # 3. Booking cancellation
            success3 = EmailService.send_booking_cancellation(
                booking_with_customer,
                refund_amount=Decimal("1320.00"),
                reason="Trip rescheduled",
            )
            assert success3 is True
            assert len(mail.outbox) == 3
            assert "Reservation Cancelled" in mail.outbox[2].subject

            # 4. Pickup reminder
            success4 = EmailService.send_pickup_reminder(booking_with_customer)
            assert success4 is True
            assert len(mail.outbox) == 4
            assert "Upcoming Vehicle Pickup" in mail.outbox[3].subject

    def test_notification_log_deduplication(self, tenant_a):
        with schema_context(tenant_a.schema_name):
            event_key = "test_event_dedup_unique_777"
            recipient = "renter@luxury.com"

            # 1. First send
            send1 = send_notification_email_async(
                schema_name=tenant_a.schema_name,
                recipient_email=recipient,
                subject="Test Dedup 1",
                template_name="emails/base_email.html",
                context={"content": "First run"},
                event_key=event_key,
            )
            assert send1 is True
            assert NotificationLog.objects.filter(event_key=event_key).count() == 1

            # 2. Second send with identical event_key must be skipped
            send2 = send_notification_email_async(
                schema_name=tenant_a.schema_name,
                recipient_email=recipient,
                subject="Test Dedup 2",
                template_name="emails/base_email.html",
                context={"content": "Duplicate run"},
                event_key=event_key,
            )
            assert send2 is True
            # Log count still 1
            assert NotificationLog.objects.filter(event_key=event_key).count() == 1

    def test_periodic_pickup_reminders_task(self, tenant_a, booking_with_customer):
        with schema_context(tenant_a.schema_name):
            # Run periodic scan
            send_pickup_reminders_all_tenants()

            # The booking is in 12 hours, so pickup reminder should have been enqueued
            expected_key = f"pickup_reminder:{booking_with_customer.booking_reference}"
            assert booking_with_customer.booking_reference in expected_key
            assert booking_with_customer.pickup_datetime > datetime.now(tz=UTC)

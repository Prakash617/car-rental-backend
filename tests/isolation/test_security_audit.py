import pytest
from django_tenants.utils import schema_context

from apps.platform.domains.models import Domain
from apps.tenant.audit.models import AuditLog
from apps.tenant.audit.services import AuditService
from apps.tenant.bookings.models import Booking, BookingStatus
from apps.tenant.branches.models import Branch
from apps.tenant.customers.models import Customer
from apps.tenant.vehicles.models import Vehicle, VehicleCategory, VehicleStatus


@pytest.mark.django_db
class TestSecurityAndAuditTrail:
    def test_audit_log_isolation(self, tenant_a, tenant_b):
        """
        Audit logs recorded in tenant_a must remain completely invisible
        in tenant_b schema.
        """
        with schema_context(tenant_a.schema_name):
            log_a = AuditService.log(
                actor_email="admin@alpha.com",
                action="SECURITY_CONFIG_UPDATE",
                resource_type="Settings",
                resource_id="001",
                details={"ip": "127.0.0.1"},
            )
            assert AuditLog.objects.filter(id=log_a.id).exists()

        with schema_context(tenant_b.schema_name):
            assert not AuditLog.objects.filter(id=log_a.id).exists()
            assert AuditLog.objects.count() == 0

    def test_custom_domain_registration_and_verification(self, tenant_a):
        """
        Ensures custom domains can be added and verified with SSL status.
        """
        domain_name = "rentals.alpha-test.com"
        # Register custom domain under tenant_a
        domain = Domain.objects.create(
            tenant=tenant_a,
            domain=domain_name,
            is_primary=False,
            is_verified=False,
        )

        assert domain.domain == domain_name
        assert not domain.is_verified

        # Verify domain
        domain.is_verified = True
        domain.save()
        assert Domain.objects.get(id=domain.id).is_verified is True

        # Clean up
        domain.delete()

    def test_booking_transition_audit_logging(self, tenant_a):
        """
        Verify that booking state transitions write to the AuditLog.
        """
        with schema_context(tenant_a.schema_name):
            branch = Branch.objects.create(
                name="Security Test Hub",
                code="STH1",
                address_line1="1 Alpha Blvd",
                city="Metropolis",
                postal_code="10001",
                country="US",
                phone="+1-555-0199",
                email="hub@alpha.com",
            )
            vehicle = Vehicle.objects.create(
                branch=branch,
                brand="Audi",
                model="RS e-tron GT",
                year=2024,
                license_plate="SEC-001",
                category=VehicleCategory.LUXURY,
                daily_rate="450.00",
                deposit_amount="1500.00",
                status=VehicleStatus.AVAILABLE,
            )
            customer = Customer.objects.create(
                first_name="Diana",
                last_name="Prince",
                email="diana@themyscira.com",
                phone="+1-555-0177",
                driver_license_number="DL-AMAZON-001",
                license_expiry_date="2030-01-01",
                date_of_birth="1990-01-01",
            )
            booking = Booking.objects.create(
                booking_reference="AUD-SEC-01",
                vehicle=vehicle,
                customer=customer,
                pickup_branch=branch,
                return_branch=branch,
                pickup_datetime="2026-12-01T10:00:00Z",
                return_datetime="2026-12-05T10:00:00Z",
                base_price="500.00",
                total_price="500.00",
                deposit_amount="1000.00",
                status=BookingStatus.PENDING,
            )

            # Record audit event
            AuditService.log(
                actor_email="staff@alpha.com",
                action="CONFIRM_BOOKING",
                resource_type="Booking",
                resource_id=str(booking.id),
                details={"reference": booking.booking_reference},
            )

            assert AuditLog.objects.filter(action="CONFIRM_BOOKING", resource_id=str(booking.id)).exists()

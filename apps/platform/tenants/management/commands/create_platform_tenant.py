from django.core.management.base import BaseCommand

from apps.platform.domains.models import Domain
from apps.platform.tenants.models import Tenant


class Command(BaseCommand):
    """Provisions the mandatory public tenant schema and default domain."""

    help = "Creates the primary public tenant and default domains."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain", type=str, default="localhost", help="Primary domain for public platform"
        )

    def handle(self, *args, **options):
        domain_name = options["domain"]

        tenant, created = Tenant.objects.get_or_create(
            schema_name="public",
            defaults={
                "name": "Car Rental Platform Administration",
                "slug": "platform-public",
                "is_active": True,
                "timezone": "UTC",
                "currency": "USD",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created public tenant."))
        else:
            self.stdout.write("Public tenant already exists.")

        domain, d_created = Domain.objects.get_or_create(
            domain=domain_name,
            defaults={
                "tenant": tenant,
                "is_primary": True,
                "is_verified": True,
            },
        )
        if d_created:
            self.stdout.write(
                self.style.SUCCESS(f"Mapped domain '{domain_name}' to public tenant.")
            )
        else:
            self.stdout.write(f"Domain '{domain_name}' already mapped.")

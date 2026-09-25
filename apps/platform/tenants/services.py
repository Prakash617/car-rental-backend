import logging

from django.db import connection, transaction
from django_tenants.utils import schema_context

from apps.platform.domains.models import Domain
from apps.platform.platform_users.models import PlatformUser
from apps.platform.tenants.models import Tenant
from apps.tenant.memberships.models import Membership, RoleChoices

logger = logging.getLogger(__name__)


class TenantProvisioningService:
    @classmethod
    def provision_tenant(cls, validated_data: dict) -> dict:
        """
        Atomically provisions a new tenant:
        1. Creates or resolves PlatformUser in public schema.
        2. Creates Tenant record and triggers PostgreSQL schema generation.
        3. Maps default subdomain.
        4. Activates tenant schema and creates Owner Membership.
        """
        # Ensure we are in the public schema when provisioning a tenant
        connection.set_schema_to_public()

        email = validated_data["email"].lower().strip()
        subdomain = validated_data["subdomain"].lower().strip()
        schema_name = f"tenant_{subdomain.replace('-', '_')}"

        with transaction.atomic():
            # 1. Resolve or create PlatformUser
            user = PlatformUser.objects.filter(email=email).first()
            if not user:
                user = PlatformUser.objects.create_user(
                    email=email,
                    password=validated_data["password"],
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    phone_number=validated_data.get("phone_number", ""),
                )

            # 2. Create Tenant (triggers PostgreSQL schema creation automatically)
            tenant = Tenant.objects.create(
                schema_name=schema_name,
                name=validated_data["company_name"],
                slug=subdomain,
                timezone=validated_data.get("timezone", "UTC"),
                currency=validated_data.get("currency", "USD"),
                is_active=True,
            )

            # 3. Create primary Domain mapping (subdomain.localhost for zero-config local access)
            domain_name = f"{subdomain}.localhost"
            domain = Domain.objects.create(
                domain=domain_name,
                tenant=tenant,
                is_primary=True,
                is_verified=True,
            )
            # Also create fallback platform.local domain
            Domain.objects.create(
                domain=f"{subdomain}.platform.local",
                tenant=tenant,
                is_primary=False,
                is_verified=True,
            )

        # 4. In tenant schema context, initialize owner membership
        with schema_context(tenant.schema_name):
            membership = Membership.objects.create(
                user_id=user.id,
                role=RoleChoices.OWNER,
                is_active=True,
            )

        logger.info(f"Successfully provisioned tenant {tenant.schema_name} with owner {user.email}")
        return {
            "tenant": tenant,
            "domain": domain,
            "user": user,
            "membership": membership,
        }

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.platform.domains.models import Domain
from apps.platform.platform_users.models import PlatformUser
from apps.platform.tenants.models import Tenant


@pytest.fixture(autouse=True)
def reset_schema_to_public(db):
    connection.set_schema_to_public()
    yield
    connection.set_schema_to_public()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def public_tenant(db):
    tenant, _ = Tenant.objects.get_or_create(
        schema_name="public",
        defaults={
            "name": "Platform Administration",
            "slug": "platform-admin",
            "is_active": True,
        },
    )
    Domain.objects.get_or_create(
        domain="localhost",
        defaults={
            "tenant": tenant,
            "is_primary": True,
            "is_verified": True,
        },
    )
    return tenant


@pytest.fixture
def tenant_a(db, public_tenant):
    tenant, _ = Tenant.objects.get_or_create(
        schema_name="tenant_alpha",
        defaults={
            "name": "Alpha Luxury Rentals",
            "slug": "alpha-luxury",
            "is_active": True,
            "timezone": "UTC",
            "currency": "USD",
        },
    )
    Domain.objects.get_or_create(
        domain="alpha.platform.local",
        defaults={
            "tenant": tenant,
            "is_primary": True,
            "is_verified": True,
        },
    )
    return tenant


@pytest.fixture
def tenant_b(db, public_tenant):
    tenant, _ = Tenant.objects.get_or_create(
        schema_name="tenant_beta",
        defaults={
            "name": "Beta Mountain Motors",
            "slug": "beta-motors",
            "is_active": True,
            "timezone": "UTC",
            "currency": "EUR",
        },
    )
    Domain.objects.get_or_create(
        domain="beta.platform.local",
        defaults={
            "tenant": tenant,
            "is_primary": True,
            "is_verified": True,
        },
    )
    return tenant


@pytest.fixture
def superuser(db):
    return PlatformUser.objects.create_superuser(
        email="superadmin@platform.com",
        password="SecureSuperPass123!",
        first_name="Super",
        last_name="Admin",
    )

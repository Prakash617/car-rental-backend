import pytest
from django.core.cache import cache
from django.db import connection
from django_tenants.utils import schema_context

from apps.platform.domains.models import Domain
from apps.tenant.bookings.tasks import check_overdue_rentals_all_tenants


@pytest.mark.django_db
class TestInfrastructureFoundation:
    def test_tenant_creation_provisions_schema(self, tenant_a):
        """Verifies that a tenant record exists and has an associated schema name."""
        assert tenant_a.schema_name == "tenant_alpha"
        assert tenant_a.name == "Alpha Luxury Rentals"
        assert tenant_a.is_active is True

        # Verify schema exists in PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                [tenant_a.schema_name],
            )
            row = cursor.fetchone()
            assert row is not None, f"Schema {tenant_a.schema_name} should exist in PostgreSQL"

    def test_domain_mapping_and_resolution(self, tenant_a, tenant_b):
        """Verifies domains uniquely resolve to their respective tenants."""
        domain_a = Domain.objects.get(domain="alpha.platform.local")
        domain_b = Domain.objects.get(domain="beta.platform.local")

        assert domain_a.tenant == tenant_a
        assert domain_b.tenant == tenant_b
        assert domain_a.tenant != domain_b.tenant

    def test_redis_cache_tenant_partitioning(self, tenant_a, tenant_b):
        """
        Verifies that Redis keys partitioned by tenant prefix
        never leak data between tenants.
        """
        key_tenant_a = f"tenant:{tenant_a.id}:fleet_count"
        key_tenant_b = f"tenant:{tenant_b.id}:fleet_count"

        cache.set(key_tenant_a, 42, timeout=60)
        cache.set(key_tenant_b, 108, timeout=60)

        assert cache.get(key_tenant_a) == 42
        assert cache.get(key_tenant_b) == 108
        assert cache.get(key_tenant_a) != cache.get(key_tenant_b)

    def test_celery_schema_context_execution(self, tenant_a):
        """Verifies code execution inside a tenant schema context."""
        with schema_context(tenant_a.schema_name):
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                assert tenant_a.schema_name in search_path

    def test_celery_overdue_task_execution(self, tenant_a, tenant_b):
        """Verifies Celery Beat task executes without unhandled exceptions."""
        result = check_overdue_rentals_all_tenants()
        assert result is None  # Completed cleanly

    def test_public_health_endpoint(self, api_client, public_tenant):
        """Verifies public healthcheck endpoint returns HTTP 200."""
        response = api_client.get("/health/", HTTP_HOST="localhost")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["scope"] == "public"

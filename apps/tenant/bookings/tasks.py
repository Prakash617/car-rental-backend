import logging

from celery import shared_task
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_rentals_all_tenants():
    """
    Periodic Celery Beat task that iterates through all active tenants
    and executes overdue return checks within each tenant schema.
    """
    TenantModel = get_tenant_model()
    # Exclude public schema
    tenants = TenantModel.objects.filter(is_active=True).exclude(schema_name="public")

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                logger.info(f"Checking overdue rentals for tenant: {tenant.schema_name}")
                # Business logic in tenant schema will be executed here
        except Exception as e:
            logger.error(f"Error checking overdue rentals for {tenant.schema_name}: {e}")

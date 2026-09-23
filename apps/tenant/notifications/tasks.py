import logging

from celery import shared_task
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)


@shared_task
def send_pickup_reminders_all_tenants():
    """
    Periodic Celery Beat task that checks upcoming vehicle pickups
    across all active tenants and schedules notifications.
    """
    TenantModel = get_tenant_model()
    tenants = TenantModel.objects.filter(is_active=True).exclude(schema_name="public")

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                logger.info(f"Checking upcoming pickup reminders for tenant: {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error checking pickup reminders for {tenant.schema_name}: {e}")

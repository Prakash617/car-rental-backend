import uuid

from django.db import models
from django_tenants.models import TenantMixin


class Tenant(TenantMixin):
    """
    Master Tenant Model stored exclusively in the public schema.
    Each instance represents an independent car rental company with its own PostgreSQL schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Company Name", max_length=120)
    slug = models.SlugField("Tenant Slug", unique=True, max_length=63)
    is_active = models.BooleanField("Is Active", default=True)
    timezone = models.CharField("Timezone", max_length=50, default="UTC")
    currency = models.CharField("Currency Code", max_length=3, default="USD")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Automatically create PostgreSQL schema on save
    auto_create_schema = True
    # Never automatically drop schema on model delete to prevent catastrophic data loss
    auto_drop_schema = False

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["schema_name"], name="idx_tenant_schema_name"),
            models.Index(fields=["slug"], name="idx_tenant_slug"),
        ]

    def __str__(self):
        return f"{self.name} ({self.schema_name})"

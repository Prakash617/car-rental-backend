import uuid

from django.db import models
from django_tenants.models import DomainMixin


class Domain(DomainMixin):
    """
    Domain Model mapping HTTP Host headers to specific tenants.
    Stored exclusively in the public schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_verified = models.BooleanField("Domain Verified", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Domain"
        verbose_name_plural = "Domains"
        ordering = ["-is_primary", "domain"]
        indexes = [
            models.Index(fields=["domain"], name="idx_domain_domain"),
        ]

    def __str__(self):
        return f"{self.domain} -> {self.tenant.schema_name}"

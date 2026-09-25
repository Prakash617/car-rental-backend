import uuid
from django.db import models


class AuditLog(models.Model):
    """
    Immutable audit trail recording security events, state changes,
    and administrative operations within the tenant schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_email = models.CharField("Actor Email", max_length=255, blank=True)
    action = models.CharField("Action", max_length=100)
    resource_type = models.CharField("Resource Type", max_length=100)
    resource_id = models.CharField("Resource ID", max_length=255, blank=True)
    details = models.JSONField("Event Details", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP Address", null=True, blank=True)
    timestamp = models.DateTimeField("Timestamp", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["resource_type", "action"], name="idx_audit_resource_action"),
            models.Index(fields=["timestamp"], name="idx_audit_timestamp"),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.actor_email} - {self.action} {self.resource_type} ({self.resource_id})"

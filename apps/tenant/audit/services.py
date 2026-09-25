from .models import AuditLog


class AuditService:
    @classmethod
    def log(
        cls,
        actor_email: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        return AuditLog.objects.create(
            actor_email=actor_email or "system@platform.local",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=details or {},
            ip_address=ip_address,
        )

import uuid

from django.db import models


class RoleChoices(models.TextChoices):
    OWNER = "owner", "Tenant Owner"
    ADMIN = "admin", "Tenant Admin"
    MANAGER = "manager", "Fleet Manager"
    STAFF = "staff", "Rental Desk Staff"
    ACCOUNTANT = "accountant", "Financial Accountant"
    VIEWER = "viewer", "Read-Only Viewer"


class Membership(models.Model):
    """
    Tenant-specific membership model stored in each tenant schema (tenant_x).
    Associates a global PlatformUser with a role in this tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Logical foreign key referencing public.platform_users_platformuser(id)
    user_id = models.UUIDField(db_index=True, null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.VIEWER,
    )
    is_active = models.BooleanField(default=True)

    # Invitation tracking
    invited_email = models.EmailField(max_length=255, null=True, blank=True)
    invitation_token = models.CharField(max_length=100, null=True, blank=True, unique=True)
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id"],
                condition=models.Q(user_id__isnull=False),
                name="unique_user_per_tenant",
            )
        ]

    def __str__(self):
        user_repr = str(self.user_id) if self.user_id else self.invited_email
        return f"{user_repr} -> {self.role} (active={self.is_active})"

    def get_user(self):
        """Fetches the global PlatformUser instance from the public schema."""
        if not self.user_id:
            return None
        from apps.platform.platform_users.models import PlatformUser

        try:
            return PlatformUser.objects.get(id=self.user_id)
        except PlatformUser.DoesNotExist:
            return None

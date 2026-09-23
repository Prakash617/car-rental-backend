from rest_framework.permissions import BasePermission

from apps.tenant.memberships.models import RoleChoices


class IsPlatformAdmin(BasePermission):
    """Allows access only to global platform administrators."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_platform_admin", False)
        )


def _resolve_tenant_membership(request):
    membership = getattr(request, "tenant_membership", None)
    if membership is None and request.user and request.user.is_authenticated:
        tenant = getattr(request, "tenant", None)
        if tenant and tenant.schema_name != "public":
            from apps.tenant.memberships.models import Membership

            membership = Membership.objects.filter(user_id=request.user.id, is_active=True).first()
            request.tenant_membership = membership
            if membership:
                request.tenant_role = membership.role
    return membership


class IsTenantMember(BasePermission):
    """
    Validates that the authenticated user possesses an active membership
    in the current tenant schema.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if getattr(request.user, "is_platform_admin", False):
            return True

        membership = _resolve_tenant_membership(request)
        return bool(membership and membership.is_active)


class HasTenantRole(BasePermission):
    """
    Factory / permission class validating that the user's role in the active tenant
    is one of the permitted roles.
    """

    allowed_roles: list[str] = []

    def __init__(self, allowed_roles: list[str] | None = None):
        if allowed_roles is not None:
            self.allowed_roles = allowed_roles

    def __call__(self):
        return self

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins bypass tenant role restrictions
        if getattr(request.user, "is_platform_admin", False):
            return True

        membership = _resolve_tenant_membership(request)
        if not membership or not membership.is_active:
            return False

        permitted = getattr(view, "allowed_roles", self.allowed_roles)
        return membership.role in permitted


class IsTenantOwnerOrAdmin(HasTenantRole):
    allowed_roles = [RoleChoices.OWNER, RoleChoices.ADMIN]


class IsTenantManagerOrAbove(HasTenantRole):
    allowed_roles = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.MANAGER]


class IsTenantStaffOrAbove(HasTenantRole):
    allowed_roles = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.MANAGER, RoleChoices.STAFF]

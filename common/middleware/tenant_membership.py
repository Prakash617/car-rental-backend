from apps.tenant.memberships.models import Membership


class TenantMembershipMiddleware:
    """
    Middleware executing after authentication to resolve the active user's
    membership and role within the currently active tenant schema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant_membership = None
        request.tenant_role = None

        tenant = getattr(request, "tenant", None)
        user = getattr(request, "user", None)

        if tenant and tenant.schema_name != "public" and user and user.is_authenticated:
            try:
                membership = Membership.objects.filter(user_id=user.id, is_active=True).first()
                if membership:
                    request.tenant_membership = membership
                    request.tenant_role = membership.role
            except Exception:
                # If table does not exist or schema is in flux, fail safely
                request.tenant_membership = None
                request.tenant_role = None

        return self.get_response(request)

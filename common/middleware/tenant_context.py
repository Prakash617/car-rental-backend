import logging

logger = logging.getLogger(__name__)

class TenantContextMiddleware:
    """
    Middleware executing after TenantMainMiddleware to attach tenant metadata
    to the active request context and verify tenant active status.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant:
            request.tenant_schema = tenant.schema_name
            request.tenant_timezone = getattr(tenant, "timezone", "UTC")
            request.tenant_currency = getattr(tenant, "currency", "USD")
        else:
            request.tenant_schema = "public"
            request.tenant_timezone = "UTC"
            request.tenant_currency = "USD"

        return self.get_response(request)

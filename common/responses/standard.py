from rest_framework.response import Response


class StandardResponseMixin:
    """
    Mixin that wraps standard ViewSet responses in the platform envelope:
    { "success": True, "data": ... }
    """

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response) and response.status_code < 400:
            if isinstance(response.data, dict) and "success" in response.data:
                return super().finalize_response(request, response, *args, **kwargs)
            response.data = {
                "success": True,
                "data": response.data,
            }
        return super().finalize_response(request, response, *args, **kwargs)

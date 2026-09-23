from typing import Any

from rest_framework import status
from rest_framework.response import Response


class StandardResponseMixin:
    """
    Mixin that standardizes APIView and ViewSet responses in the platform envelope:
    { "success": True, "data": ..., "message": ... }
    """

    def success_response(
        self,
        data: Any = None,
        message: str | None = None,
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        body: dict[str, Any] = {"success": True, "data": data}
        if message:
            body["message"] = message
        return Response(body, status=status_code)

    def error_response(
        self,
        message: str = "An error occurred",
        errors: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> Response:
        body: dict[str, Any] = {"success": False, "message": message}
        if errors:
            body["errors"] = errors
        return Response(body, status=status_code)

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response) and response.status_code < 400:
            if isinstance(response.data, dict) and "success" in response.data:
                return super().finalize_response(request, response, *args, **kwargs)
            response.data = {
                "success": True,
                "data": response.data,
            }
        return super().finalize_response(request, response, *args, **kwargs)

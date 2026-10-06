import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code == 404:
            error_code = "NOT_FOUND"
        elif response.status_code == 403:
            error_code = "PERMISSION_DENIED"
        elif response.status_code == 401:
            error_code = "UNAUTHENTICATED"
        else:
            error_code = getattr(exc, "default_code", "API_ERROR")
            if isinstance(error_code, str):
                error_code = error_code.upper()
            else:
                error_code = "API_ERROR"

        if isinstance(response.data, dict):
            message = response.data.get("detail", str(response.data))
            details = response.data if "detail" not in response.data else None
        elif isinstance(response.data, list):
            message = response.data[0] if response.data else "Validation error"
            details = response.data
        else:
            message = str(response.data)
            details = None

        response.data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": details,
            },
        }
    else:
        logger.exception("Unhandled server exception: %s", exc)
        response = Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response

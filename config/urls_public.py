from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def public_health_check(request):
    return JsonResponse(
        {"status": "healthy", "service": "car-rental-saas-platform", "scope": "public"}
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", public_health_check, name="public_health_check"),
]

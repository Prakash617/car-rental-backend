from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.platform.platform_users.views import CurrentUserView, LoginView, RegisterTenantView
from apps.platform.tenants.views import (
    PlatformOverviewView,
    PlatformTenantDetailView,
    PlatformTenantListView,
)


def public_health_check(request):
    return JsonResponse(
        {
            "status": "healthy",
            "service": "car-rental-saas-platform",
            "scope": "public",
        }
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", public_health_check, name="public_health_check"),
    # Public Auth & Onboarding
    path("api/v1/auth/register/", RegisterTenantView.as_view(), name="auth_register_tenant"),
    path("api/v1/auth/login/", LoginView.as_view(), name="auth_login_public"),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh_public"),
    path("api/v1/auth/me/", CurrentUserView.as_view(), name="auth_me_public"),
    # Platform Super-Admin Endpoints
    path("api/v1/platform/overview/", PlatformOverviewView.as_view(), name="platform_overview"),
    path("api/v1/platform/tenants/", PlatformTenantListView.as_view(), name="platform_tenants_list"),
    path(
        "api/v1/platform/tenants/<uuid:pk>/",
        PlatformTenantDetailView.as_view(),
        name="platform_tenant_detail",
    ),
]

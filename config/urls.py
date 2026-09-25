from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.platform.platform_users.views import CurrentUserView, LoginView
from apps.tenant.bookings.views import BookingViewSet, QuoteView
from apps.tenant.branches.views import BranchViewSet
from apps.tenant.customers.views import CustomerViewSet
from apps.tenant.memberships.views import AcceptInviteView, InviteMemberView, TeamMemberListView
from apps.tenant.pricing.views import (
    CouponViewSet,
    ExtraAddonViewSet,
    SeasonalRateViewSet,
)
from apps.tenant.reports.views import DashboardOverviewView
from apps.tenant.vehicles.views import VehicleViewSet
from apps.tenant.websites.views import (
    CustomPageDetailView,
    CustomPageListCreateView,
    FAQListCreateView,
    FAQManageView,
    ManageCustomPageListView,
    ManageWebsiteConfigView,
    PublicWebsiteConfigView,
)

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"vehicles", VehicleViewSet, basename="vehicle")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"pricing/seasonal-rates", SeasonalRateViewSet, basename="seasonal-rate")
router.register(r"pricing/coupons", CouponViewSet, basename="coupon")
router.register(r"pricing/addons", ExtraAddonViewSet, basename="addon")

urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI Documentation
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Tenant Auth
    path("api/v1/auth/login/", LoginView.as_view(), name="auth_login_tenant"),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh_tenant"),
    path("api/v1/auth/me/", CurrentUserView.as_view(), name="auth_me_tenant"),
    # Team & Memberships
    path("api/v1/team/", TeamMemberListView.as_view(), name="team_list"),
    path("api/v1/team/invite/", InviteMemberView.as_view(), name="team_invite"),
    path("api/v1/team/accept-invite/", AcceptInviteView.as_view(), name="team_accept_invite"),
    # Website & Themes
    path("api/v1/website/config/", PublicWebsiteConfigView.as_view(), name="website_config_public"),
    path("api/v1/dashboard/theme/", ManageWebsiteConfigView.as_view(), name="dashboard_theme"),
    # FAQ (public GET, staff POST/PATCH/DELETE)
    path("api/v1/website/faq/", FAQListCreateView.as_view(), name="website_faq_list"),
    path("api/v1/dashboard/faq/<uuid:pk>/", FAQManageView.as_view(), name="dashboard_faq_manage"),
    # Custom Pages (public GET by slug, staff write)
    path("api/v1/website/pages/", CustomPageListCreateView.as_view(), name="website_pages_list"),
    path("api/v1/website/pages/<slug:slug>/", CustomPageDetailView.as_view(), name="website_page_detail"),
    path("api/v1/dashboard/pages/", ManageCustomPageListView.as_view(), name="dashboard_pages_manage"),
    # Dashboard Analytics
    path("api/v1/dashboard/overview/", DashboardOverviewView.as_view(), name="dashboard_overview"),
    # Pricing Quote
    path("api/v1/pricing/quote/", QuoteView.as_view(), name="pricing_quote"),
    # Payments
    path("api/v1/payments/", include("apps.tenant.payments.urls")),
    # Notifications
    path("api/v1/notifications/", include("apps.tenant.notifications.urls")),
    # Fleet Maintenance & Telemetry
    path("api/v1/maintenance/", include("apps.tenant.maintenance.urls")),
    # Core Rental API & CRUD ViewSets
    path("api/v1/", include(router.urls)),
]

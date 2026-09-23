from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.platform.platform_users.views import CurrentUserView, LoginView
from apps.tenant.memberships.views import AcceptInviteView, InviteMemberView, TeamMemberListView

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
]

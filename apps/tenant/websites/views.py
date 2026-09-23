from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.views import APIView

from common.permissions.tenant import IsTenantOwnerOrAdmin
from common.responses.standard import StandardResponseMixin

from .models import WebsiteConfig
from .serializers import WebsiteConfigSerializer


class PublicWebsiteConfigView(StandardResponseMixin, APIView):
    """
    Public endpoint providing tenant website configuration, theme selection,
    color palettes, contact numbers, and SEO metadata.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: WebsiteConfigSerializer})
    def get(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(config, context={"request": request})
        return self.success_response(
            data=serializer.data,
            message="Tenant website configuration retrieved successfully",
        )


class ManageWebsiteConfigView(StandardResponseMixin, APIView):
    """
    Tenant admin dashboard endpoint for updating branding, active theme,
    accent colors, and marketing hero content.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantOwnerOrAdmin]

    @extend_schema(responses={200: WebsiteConfigSerializer})
    def get(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(config, context={"request": request})
        return self.success_response(data=serializer.data)

    @extend_schema(request=WebsiteConfigSerializer, responses={200: WebsiteConfigSerializer})
    def patch(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=serializer.data,
            message="Website branding and theme updated successfully",
        )

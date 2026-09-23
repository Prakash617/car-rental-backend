from rest_framework import permissions, viewsets

from common.permissions.tenant import IsTenantManagerOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Coupon, ExtraAddon, SeasonalRate
from .serializers import (
    CouponSerializer,
    ExtraAddonSerializer,
    SeasonalRateSerializer,
)


class SeasonalRateViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Seasonal price multipliers management for managers and administrators.
    """

    queryset = SeasonalRate.objects.all()
    serializer_class = SeasonalRateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantManagerOrAbove]
    filterset_fields = ["is_active"]
    ordering_fields = ["start_date", "end_date", "multiplier"]
    ordering = ["start_date"]


class CouponViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Promotional voucher codes management.
    """

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantManagerOrAbove]
    filterset_fields = ["is_active", "discount_type"]
    search_fields = ["code"]
    ordering_fields = ["created_at", "valid_to"]
    ordering = ["-created_at"]


class ExtraAddonViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Add-on extras (GPS, Child Seat, Damage Waiver).
    Public renters can list and view active add-ons during checkout.
    Mutations require Manager role.
    """

    queryset = ExtraAddon.objects.all()
    serializer_class = ExtraAddonSerializer
    filterset_fields = ["is_active", "pricing_type"]
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantManagerOrAbove()]

    def get_queryset(self):
        if self.action in ["list", "retrieve"]:
            return ExtraAddon.objects.filter(is_active=True)
        return ExtraAddon.objects.all()

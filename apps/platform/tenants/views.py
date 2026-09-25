from decimal import Decimal
from django_tenants.utils import schema_context
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions.tenant import IsPlatformAdmin
from common.responses.standard import StandardResponseMixin

from .models import Tenant
from .serializers import (
    PlatformTenantSerializer,
    ProvisionTenantSerializer,
    UpdatePlatformTenantSerializer,
)
from .services import TenantProvisioningService


class PlatformOverviewView(StandardResponseMixin, APIView):
    """
    Platform executive metrics: total tenants, fleet under management,
    global bookings, and platform revenue.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        tenants = Tenant.objects.exclude(schema_name="public")
        total_tenants = tenants.count()
        active_tenants = tenants.filter(is_active=True).count()

        total_vehicles = 0
        total_bookings = 0
        total_revenue = Decimal("0.00")

        from apps.tenant.bookings.models import Booking, PaymentStatus
        from apps.tenant.vehicles.models import Vehicle

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    total_vehicles += Vehicle.objects.count()
                    total_bookings += Booking.objects.count()
                    # Calculate revenue for paid bookings
                    paid_bookings = Booking.objects.filter(payment_status=PaymentStatus.PAID)
                    for b in paid_bookings:
                        total_revenue += b.total_price
            except Exception:
                continue

        return self.success_response(
            data={
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "total_fleets": total_vehicles,
                "total_bookings": total_bookings,
                "total_revenue": str(total_revenue),
                "platform_health": "operational",
            }
        )


class PlatformTenantListView(StandardResponseMixin, APIView):
    """
    Platform Super-Admin endpoints for listing and provisioning tenants.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(responses={200: PlatformTenantSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        tenants = Tenant.objects.exclude(schema_name="public").order_by("-created_at")
        serializer = PlatformTenantSerializer(tenants, many=True)
        return self.success_response(data=serializer.data)

    @extend_schema(request=ProvisionTenantSerializer, responses={201: PlatformTenantSerializer})
    def post(self, request, *args, **kwargs):
        serializer = ProvisionTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = TenantProvisioningService.provision_tenant(serializer.validated_data)
        out_serializer = PlatformTenantSerializer(result["tenant"])
        return self.success_response(
            data=out_serializer.data,
            message=f"Tenant '{result['tenant'].name}' provisioned successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class PlatformTenantDetailView(StandardResponseMixin, APIView):
    """
    Platform Super-Admin: inspect or update tenant status (e.g. suspend/reactivate).
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get_object(self, pk):
        try:
            return Tenant.objects.exclude(schema_name="public").get(pk=pk)
        except Tenant.DoesNotExist:
            return None

    @extend_schema(responses={200: PlatformTenantSerializer})
    def get(self, request, pk, *args, **kwargs):
        tenant = self.get_object(pk)
        if not tenant:
            return self.error_response("Tenant not found", status_code=status.HTTP_404_NOT_FOUND)
        return self.success_response(data=PlatformTenantSerializer(tenant).data)

    @extend_schema(request=UpdatePlatformTenantSerializer, responses={200: PlatformTenantSerializer})
    def patch(self, request, pk, *args, **kwargs):
        tenant = self.get_object(pk)
        if not tenant:
            return self.error_response("Tenant not found", status_code=status.HTTP_404_NOT_FOUND)
        serializer = UpdatePlatformTenantSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=PlatformTenantSerializer(tenant).data,
            message="Tenant updated successfully.",
        )

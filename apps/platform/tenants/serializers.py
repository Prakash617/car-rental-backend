from rest_framework import serializers

from apps.platform.domains.models import Domain
from apps.platform.tenants.models import Tenant


class PlatformTenantSerializer(serializers.ModelSerializer):
    primary_domain = serializers.SerializerMethodField()
    vehicle_count = serializers.SerializerMethodField()
    booking_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "schema_name",
            "is_active",
            "timezone",
            "currency",
            "primary_domain",
            "vehicle_count",
            "booking_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "schema_name", "created_at", "updated_at"]

    def get_primary_domain(self, obj):
        domain = obj.domains.filter(is_primary=True).first()
        if domain:
            return domain.domain
        first = obj.domains.first()
        return first.domain if first else f"{obj.slug}.localhost"

    def get_vehicle_count(self, obj):
        if obj.schema_name == "public":
            return 0
        from django_tenants.utils import schema_context
        from apps.tenant.vehicles.models import Vehicle

        try:
            with schema_context(obj.schema_name):
                return Vehicle.objects.count()
        except Exception:
            return 0

    def get_booking_count(self, obj):
        if obj.schema_name == "public":
            return 0
        from django_tenants.utils import schema_context
        from apps.tenant.bookings.models import Booking

        try:
            with schema_context(obj.schema_name):
                return Booking.objects.count()
        except Exception:
            return 0


class ProvisionTenantSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=150)
    subdomain = serializers.SlugField(max_length=63)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=60, default="Admin")
    last_name = serializers.CharField(max_length=60, default="Owner")
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    currency = serializers.CharField(max_length=10, default="USD")
    timezone = serializers.CharField(max_length=50, default="UTC")

    def validate_subdomain(self, value):
        val = value.lower().strip()
        forbidden = ["public", "admin", "platform", "api", "www", "mail", "localhost", "test"]
        if val in forbidden:
            raise serializers.ValidationError(f"'{val}' is a reserved subdomain.")
        if Tenant.objects.filter(slug=val).exists():
            raise serializers.ValidationError(f"Subdomain '{val}' is already taken.")
        return val


class UpdatePlatformTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["name", "is_active", "timezone", "currency"]

from rest_framework import serializers

from apps.tenant.branches.serializers import BranchSerializer
from apps.tenant.customers.serializers import CustomerSerializer
from apps.tenant.vehicles.serializers import VehicleSerializer

from .models import Booking, BookingAddon


class BookingAddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingAddon
        fields = ["id", "name", "price", "quantity"]


class BookingSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    pickup_branch = BranchSerializer(read_only=True)
    return_branch = BranchSerializer(read_only=True)
    addons = BookingAddonSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "vehicle",
            "customer",
            "pickup_branch",
            "return_branch",
            "pickup_datetime",
            "return_datetime",
            "pickup_location",
            "destination_location",
            "stops",
            "trip_type",
            "decoration_name",
            "decoration_price",
            "distance_km",
            "customer_name",
            "customer_phone",
            "customer_email",
            "advance_amount",
            "status",
            "payment_status",
            "base_price",
            "discount_amount",
            "tax_amount",
            "deposit_amount",
            "total_price",
            "notes",
            "addons",
            "created_at",
        ]
        read_only_fields = ["id", "booking_reference", "status", "payment_status", "created_at"]


class CustomerInputSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60, required=False, default="")
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    driver_license_number = serializers.CharField(max_length=50, required=False, default="SAJILO-PENDING")
    license_expiry_date = serializers.DateField(required=False, allow_null=True, default=None)
    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    country = serializers.CharField(max_length=2, default="NP")


class QuoteRequestSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    addon_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    coupon_code = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["return_datetime"] <= attrs["pickup_datetime"]:
            raise serializers.ValidationError(
                "return_datetime must be strictly after pickup_datetime."
            )
        return attrs


class CreateBookingSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    customer = CustomerInputSerializer()
    pickup_branch_id = serializers.UUIDField(required=False, allow_null=True)
    return_branch_id = serializers.UUIDField(required=False, allow_null=True)
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    pickup_location = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    destination_location = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    stops = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    trip_type = serializers.CharField(max_length=30, required=False, default="return")
    decoration_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    decoration_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    distance_km = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, default=0.00)
    advance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0.00)
    addon_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    coupon_code = serializers.CharField(max_length=30, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["return_datetime"] <= attrs["pickup_datetime"]:
            raise serializers.ValidationError(
                "return_datetime must be strictly after pickup_datetime."
            )
        return attrs

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
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    driver_license_number = serializers.CharField(max_length=50)
    license_expiry_date = serializers.DateField()
    date_of_birth = serializers.DateField()
    country = serializers.CharField(max_length=2, default="US")


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
    pickup_branch_id = serializers.UUIDField()
    return_branch_id = serializers.UUIDField()
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    addon_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    coupon_code = serializers.CharField(max_length=30, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["return_datetime"] <= attrs["pickup_datetime"]:
            raise serializers.ValidationError(
                "return_datetime must be strictly after pickup_datetime."
            )
        return attrs

from rest_framework import serializers

from apps.tenant.branches.models import Branch
from apps.tenant.branches.serializers import BranchSerializer

from .models import Category, Transmission, Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    deposit_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=0.00,
    )

    def validate(self, attrs):
        if not attrs.get("branch"):
            branch = Branch.objects.filter(is_active=True).first()
            if not branch:
                branch = Branch.objects.create(
                    name="Main Headquarters",
                    code="HQ-01",
                    address_line1="100 Grand Boulevard",
                    city="Metropolis",
                    postal_code="10001",
                    country="US",
                    phone="+1 (800) 555-0100",
                    email="hq@fleet.local",
                    is_active=True,
                )
            attrs["branch"] = branch

        if attrs.get("deposit_amount") is None:
            attrs["deposit_amount"] = 0.00

        return attrs

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "branch",
            "branch_name",
            "brand",
            "model",
            "year",
            "license_plate",
            "category",
            "transmission",
            "fuel_type",
            "seats",
            "doors",
            "mileage",
            "color",
            "status",
            "daily_rate",
            "rate_4h",
            "rate_8h",
            "fuel_rate_per_km",
            "weekly_rate",
            "monthly_rate",
            "deposit_amount",
            "is_verified",
            "driver_included",
            "driver_name",
            "driver_experience",
            "features",
            "images",
            "description",
        ]


class VehicleDetailSerializer(VehicleSerializer):
    branch = BranchSerializer(read_only=True)


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.CharField(max_length=60, required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TransmissionSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(max_length=60, required=False, allow_blank=True)

    class Meta:
        model = Transmission
        fields = ["id", "name", "slug", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

from rest_framework import serializers

from apps.tenant.branches.serializers import BranchSerializer

from .models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)

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
            "weekly_rate",
            "monthly_rate",
            "deposit_amount",
            "features",
            "images",
            "description",
        ]


class VehicleDetailSerializer(VehicleSerializer):
    branch = BranchSerializer(read_only=True)

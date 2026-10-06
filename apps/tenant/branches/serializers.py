from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="Main Depot Facility")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Metropolis")
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default="10001")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="+1 (800) 555-0100")
    email = serializers.EmailField(max_length=255, required=False, allow_blank=True, default="branch@fleet.local")

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",
            "phone",
            "email",
            "is_active",
        ]

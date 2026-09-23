from rest_framework import serializers

from .models import Coupon, ExtraAddon, SeasonalRate


class SeasonalRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonalRate
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "multiplier",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "discount_value",
            "min_rental_days",
            "max_uses",
            "times_used",
            "valid_from",
            "valid_to",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "times_used", "created_at"]


class ExtraAddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraAddon
        fields = [
            "id",
            "name",
            "description",
            "price",
            "pricing_type",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

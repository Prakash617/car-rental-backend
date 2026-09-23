from django.contrib import admin

from .models import Coupon, ExtraAddon, SeasonalRate


@admin.register(SeasonalRate)
class SeasonalRateAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "multiplier", "is_active")
    list_filter = ("is_active",)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "times_used",
        "max_uses",
        "is_active",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)


@admin.register(ExtraAddon)
class ExtraAddonAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "pricing_type", "is_active")
    list_filter = ("pricing_type", "is_active")

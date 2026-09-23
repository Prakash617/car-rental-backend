from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "brand",
        "model",
        "year",
        "license_plate",
        "category",
        "transmission",
        "daily_rate",
        "status",
        "branch",
    )
    list_filter = ("status", "category", "transmission", "fuel_type", "branch")
    search_fields = ("brand", "model", "license_plate", "vin")
    readonly_fields = ("id", "created_at", "updated_at")

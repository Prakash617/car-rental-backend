from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "driver_license_number",
        "is_verified",
        "created_at",
    )
    list_filter = ("is_verified", "country")
    search_fields = ("first_name", "last_name", "email", "driver_license_number")
    readonly_fields = ("id", "created_at", "updated_at")

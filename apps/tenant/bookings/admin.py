from django.contrib import admin

from .models import Booking, BookingAddon


class BookingAddonInline(admin.TabularInline):
    model = BookingAddon
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "vehicle",
        "customer",
        "pickup_datetime",
        "return_datetime",
        "status",
        "payment_status",
        "total_price",
    )
    list_filter = ("status", "payment_status", "pickup_branch")
    search_fields = ("booking_reference", "customer__email", "vehicle__license_plate")
    inlines = [BookingAddonInline]
    readonly_fields = ("id", "booking_reference", "created_at", "updated_at")

from django.contrib import admin

from .models import MaintenanceRecord


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "service_type", "status", "scheduled_start", "scheduled_end", "cost")
    list_filter = ("status", "service_type")
    search_fields = ("vehicle__license_plate", "service_type", "service_center")
    readonly_fields = ("id", "created_at", "updated_at")

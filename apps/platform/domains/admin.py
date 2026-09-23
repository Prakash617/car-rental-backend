from django.contrib import admin

from .models import Domain


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary", "is_verified", "created_at")
    list_filter = ("is_primary", "is_verified")
    search_fields = ("domain", "tenant__name", "tenant__schema_name")
    readonly_fields = ("id", "created_at")

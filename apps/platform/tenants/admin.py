from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "schema_name",
        "is_active",
        "timezone",
        "currency",
        "created_at",
    )
    list_filter = ("is_active", "timezone", "currency")
    search_fields = ("name", "slug", "schema_name")
    readonly_fields = ("id", "created_at", "updated_at")

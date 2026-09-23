from django.contrib import admin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "phone", "email", "is_active", "created_at")
    list_filter = ("city", "is_active")
    search_fields = ("name", "code", "city", "email")
    readonly_fields = ("id", "created_at", "updated_at")

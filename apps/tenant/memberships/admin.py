from django.contrib import admin

from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "invited_email", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("user_id", "invited_email")
    readonly_fields = ("id", "created_at", "updated_at")

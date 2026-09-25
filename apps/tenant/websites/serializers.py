from rest_framework import serializers

from .models import FAQ, CustomPage, WebsiteConfig


class WebsiteConfigSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()

    class Meta:
        model = WebsiteConfig
        fields = [
            "id",
            "name",
            "active_theme",
            "primary_color",
            "accent_color",
            "font_heading",
            "logo_url",
            "support_email",
            "support_phone",
            "currency",
            "timezone",
            "hero_title",
            "hero_subtitle",
            "seo_meta_title",
            "seo_meta_description",
            "seo_keywords",
            "og_image_url",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def get_name(self, obj):
        tenant = getattr(self.context.get("request"), "tenant", None)
        return tenant.name if tenant else "Apex Luxury Concierge"

    def get_currency(self, obj):
        tenant = getattr(self.context.get("request"), "tenant", None)
        return tenant.currency if tenant else "USD"

    def get_timezone(self, obj):
        tenant = getattr(self.context.get("request"), "tenant", None)
        return tenant.timezone if tenant else "UTC"


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = [
            "id",
            "question",
            "answer",
            "is_active",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomPage
        fields = [
            "id",
            "title",
            "slug",
            "content",
            "is_published",
            "seo_title",
            "seo_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

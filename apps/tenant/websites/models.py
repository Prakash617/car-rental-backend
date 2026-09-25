import uuid

from django.db import models


class ThemeChoice(models.TextChoices):
    LUXURY = "luxury", "Luxury Concierge"
    MODERN = "modern", "Modern Mobility"
    CLASSIC = "classic", "Heritage Classic"
    ADVENTURE = "adventure", "All-Terrain Adventure"
    URBAN = "urban", "Urban Pulse"
    MINIMAL = "minimal", "Pure Minimal"


class WebsiteConfig(models.Model):
    """
    Tenant website and branding configuration stored within each tenant schema.
    Controls public theme selection, custom colors, hero messaging, and SEO metadata.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    active_theme = models.CharField(
        "Active Theme",
        max_length=30,
        choices=ThemeChoice.choices,
        default=ThemeChoice.LUXURY,
    )
    primary_color = models.CharField(
        "Primary Accent Color (HEX)",
        max_length=20,
        default="#D4AF37",
        help_text="Hex code, e.g. #D4AF37 for luxury gold or #2563EB for electric blue",
    )
    accent_color = models.CharField(
        "Secondary Accent Color (HEX)",
        max_length=20,
        default="#B38F26",
    )
    font_heading = models.CharField(
        "Heading Font Style",
        max_length=50,
        default="serif",
        help_text="'serif' (luxury/classic) or 'sans' (modern/urban/minimal)",
    )
    logo_url = models.URLField("Brand Logo URL", blank=True, null=True)
    support_email = models.EmailField("Concierge Support Email", blank=True, null=True)
    support_phone = models.CharField(
        "Concierge Hotline Phone", max_length=30, blank=True, null=True
    )

    # Hero Banner Customization
    hero_title = models.CharField("Hero Banner Title", max_length=200, blank=True, null=True)
    hero_subtitle = models.TextField("Hero Banner Subtitle", blank=True, null=True)

    # SEO & OpenGraph
    seo_meta_title = models.CharField("SEO Meta Title", max_length=150, blank=True, null=True)
    seo_meta_description = models.TextField("SEO Meta Description", blank=True, null=True)
    seo_keywords = models.CharField("SEO Keywords", max_length=255, blank=True, null=True)

    # OG / Social image URL for rich social previews
    og_image_url = models.URLField("OpenGraph / Social Image URL", blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Website Configuration"
        verbose_name_plural = "Website Configurations"

    def __str__(self):
        return f"WebsiteConfig ({self.active_theme})"

    @classmethod
    def get_solo(cls):
        """Returns the single configuration record for this tenant schema or creates default."""
        config, _ = cls.objects.get_or_create(
            defaults={
                "active_theme": ThemeChoice.LUXURY,
                "primary_color": "#D4AF37",
                "accent_color": "#B38F26",
            }
        )
        return config


class FAQ(models.Model):
    """
    Frequently asked questions displayed on the tenant's public storefront.
    Supports ordering and is filterable by active status.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField("Question", max_length=400)
    answer = models.TextField("Answer")
    is_active = models.BooleanField("Visible on Storefront", default=True)
    order = models.PositiveSmallIntegerField(
        "Display Order",
        default=0,
        help_text="Lower number appears first in the list.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ Item"
        verbose_name_plural = "FAQ Items"
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.question[:80]


class CustomPage(models.Model):
    """
    Simple content pages managed by the tenant (Terms, Privacy Policy, About Us, etc.).
    Each page has a unique slug that maps to a public route on the storefront.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Page Title", max_length=200)
    slug = models.SlugField(
        "URL Slug",
        max_length=120,
        unique=True,
        help_text="Used in the storefront URL: /pages/<slug>",
    )
    content = models.TextField(
        "Page Content (Markdown)",
        help_text="Supports Markdown formatting.",
    )
    is_published = models.BooleanField("Published", default=False)
    seo_title = models.CharField("SEO Title Override", max_length=150, blank=True)
    seo_description = models.TextField("SEO Description Override", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Custom Page"
        verbose_name_plural = "Custom Pages"
        ordering = ["title"]

    def __str__(self):
        return self.title

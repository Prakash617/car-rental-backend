import uuid

from django.db import models


class ThemeChoice(models.TextChoices):
    SAJILO = "sajilo", "Sajilo Rental Nepal"
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
    show_in_navbar = models.BooleanField(
        "Show in Navbar",
        default=False,
        help_text="Display this page as a link in the storefront navigation bar.",
    )
    show_in_footer = models.BooleanField(
        "Show in Footer",
        default=False,
        help_text="Display this page as a link in the storefront footer.",
    )
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


class BlogPost(models.Model):
    """
    Editorial blog posts and travel guides for the tenant's public storefront.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Post Title", max_length=250)
    slug = models.SlugField(
        "URL Slug",
        max_length=150,
        unique=True,
        help_text="Unique URL identifier for the blog post: /blog/<slug>",
    )
    excerpt = models.TextField(
        "Excerpt",
        blank=True,
        help_text="Short teaser summary displayed in blog listings.",
    )
    content = models.TextField(
        "Post Content",
        help_text="Full post content with formatting or markdown support.",
    )
    cover_image = models.URLField("Cover Image URL", blank=True, null=True)
    author_name = models.CharField(
        "Author Name",
        max_length=100,
        default="Sajilo Editorial Team",
    )
    author_avatar = models.URLField("Author Avatar URL", blank=True, null=True)
    category = models.CharField(
        "Category",
        max_length=60,
        default="Travel Guide",
    )
    tags = models.CharField(
        "Tags",
        max_length=200,
        blank=True,
        help_text="Comma-separated tags (e.g. Nepal, Road Trips, Pokhara)",
    )
    read_time_minutes = models.PositiveSmallIntegerField(
        "Read Time (Minutes)",
        default=5,
    )
    is_published = models.BooleanField("Published", default=True)
    views_count = models.PositiveIntegerField("Views Count", default=0)
    published_at = models.DateTimeField("Published At", auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

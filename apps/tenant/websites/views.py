from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from common.permissions.tenant import IsTenantOwnerOrAdmin, IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import FAQ, BlogPost, CustomPage, WebsiteConfig
from .serializers import (
    BlogPostSerializer,
    CustomPageSerializer,
    FAQSerializer,
    WebsiteConfigSerializer,
)


class PublicWebsiteConfigView(StandardResponseMixin, APIView):
    """
    Public endpoint providing tenant website configuration, theme selection,
    color palettes, contact numbers, and SEO metadata.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: WebsiteConfigSerializer})
    def get(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(config, context={"request": request})
        return self.success_response(
            data=serializer.data,
            message="Tenant website configuration retrieved successfully",
        )


class ManageWebsiteConfigView(StandardResponseMixin, APIView):
    """
    Tenant admin dashboard endpoint for updating branding, active theme,
    accent colors, hero content, SEO meta, and OG image.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]

    @extend_schema(responses={200: WebsiteConfigSerializer})
    def get(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(config, context={"request": request})
        return self.success_response(data=serializer.data)

    @extend_schema(request=WebsiteConfigSerializer, responses={200: WebsiteConfigSerializer})
    def patch(self, request, *args, **kwargs):
        config = WebsiteConfig.get_solo()
        serializer = WebsiteConfigSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=serializer.data,
            message="Website branding and theme updated successfully",
        )


class FAQListCreateView(StandardResponseMixin, APIView):
    """
    Public GET (all active FAQs) + staff-authenticated POST to create a new FAQ item.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantStaffOrAbove()]

    @extend_schema(responses={200: FAQSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        """Return all active FAQ items ordered by display order."""
        faqs = FAQ.objects.filter(is_active=True)
        serializer = FAQSerializer(faqs, many=True)
        return self.success_response(data=serializer.data)

    @extend_schema(request=FAQSerializer, responses={201: FAQSerializer})
    def post(self, request, *args, **kwargs):
        """Create a new FAQ item. Requires tenant staff auth."""
        serializer = FAQSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=serializer.data,
            message="FAQ item created successfully",
            status_code=status.HTTP_201_CREATED,
        )


class FAQManageView(StandardResponseMixin, APIView):
    """
    Staff dashboard: retrieve, update, or delete a single FAQ item by UUID.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]

    def get_object(self, pk):
        try:
            return FAQ.objects.get(pk=pk)
        except FAQ.DoesNotExist:
            return None

    @extend_schema(responses={200: FAQSerializer})
    def get(self, request, pk, *args, **kwargs):
        faq = self.get_object(pk)
        if not faq:
            return self.error_response("FAQ item not found", status_code=status.HTTP_404_NOT_FOUND)
        return self.success_response(data=FAQSerializer(faq).data)

    @extend_schema(request=FAQSerializer, responses={200: FAQSerializer})
    def patch(self, request, pk, *args, **kwargs):
        faq = self.get_object(pk)
        if not faq:
            return self.error_response("FAQ item not found", status_code=status.HTTP_404_NOT_FOUND)
        serializer = FAQSerializer(faq, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(data=serializer.data, message="FAQ item updated")

    def delete(self, request, pk, *args, **kwargs):
        faq = self.get_object(pk)
        if not faq:
            return self.error_response("FAQ item not found", status_code=status.HTTP_404_NOT_FOUND)
        faq.delete()
        return self.success_response(data=None, message="FAQ item deleted")


class CustomPageListCreateView(StandardResponseMixin, APIView):
    """
    Public GET (published pages index) + staff POST to create custom page.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantStaffOrAbove()]

    @extend_schema(responses={200: CustomPageSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        pages = CustomPage.objects.filter(is_published=True)
        serializer = CustomPageSerializer(pages, many=True)
        return self.success_response(data=serializer.data)

    @extend_schema(request=CustomPageSerializer, responses={201: CustomPageSerializer})
    def post(self, request, *args, **kwargs):
        serializer = CustomPageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=serializer.data,
            message="Custom page created successfully",
            status_code=status.HTTP_201_CREATED,
        )


class CustomPageDetailView(StandardResponseMixin, APIView):
    """
    Public GET by slug (for storefront rendering) + staff PATCH/DELETE by UUID.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantStaffOrAbove()]

    def get_object_by_slug(self, slug):
        try:
            return CustomPage.objects.get(slug=slug, is_published=True)
        except CustomPage.DoesNotExist:
            return None

    def get_object_by_pk(self, pk):
        try:
            return CustomPage.objects.get(pk=pk)
        except CustomPage.DoesNotExist:
            return None

    @extend_schema(responses={200: CustomPageSerializer})
    def get(self, request, slug, *args, **kwargs):
        page = self.get_object_by_slug(slug)
        if not page:
            return self.error_response("Page not found", status_code=status.HTTP_404_NOT_FOUND)
        return self.success_response(data=CustomPageSerializer(page).data)

    @extend_schema(request=CustomPageSerializer, responses={200: CustomPageSerializer})
    def patch(self, request, slug, *args, **kwargs):
        # Staff can update by slug (which is unique)
        try:
            page = CustomPage.objects.get(slug=slug)
        except CustomPage.DoesNotExist:
            return self.error_response("Page not found", status_code=status.HTTP_404_NOT_FOUND)
        serializer = CustomPageSerializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(data=serializer.data, message="Page updated successfully")

    def delete(self, request, slug, *args, **kwargs):
        try:
            page = CustomPage.objects.get(slug=slug)
        except CustomPage.DoesNotExist:
            return self.error_response("Page not found", status_code=status.HTTP_404_NOT_FOUND)
        page.delete()
        return self.success_response(data=None, message="Page deleted")


class ManageCustomPageListView(StandardResponseMixin, APIView):
    """
    Staff-only: list ALL pages (including unpublished) for dashboard CMS management.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]

    @extend_schema(responses={200: CustomPageSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        pages = CustomPage.objects.all()
        serializer = CustomPageSerializer(pages, many=True)
        return self.success_response(data=serializer.data)


class BlogPostListCreateView(StandardResponseMixin, APIView):
    """
    Public GET (published blog articles) + staff POST to create new blog post.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantStaffOrAbove()]

    @extend_schema(responses={200: BlogPostSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        category = request.query_params.get("category")
        tag = request.query_params.get("tag")
        search = request.query_params.get("search")

        posts = BlogPost.objects.filter(is_published=True)

        if category and category != "all":
            posts = posts.filter(category__iexact=category)
        if tag:
            posts = posts.filter(tags__icontains=tag)
        if search:
            posts = posts.filter(title__icontains=search) | posts.filter(content__icontains=search)

        serializer = BlogPostSerializer(posts, many=True)
        return self.success_response(data=serializer.data)

    @extend_schema(request=BlogPostSerializer, responses={201: BlogPostSerializer})
    def post(self, request, *args, **kwargs):
        serializer = BlogPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(
            data=serializer.data,
            message="Blog post created successfully",
            status_code=status.HTTP_201_CREATED,
        )


class BlogPostDetailView(StandardResponseMixin, APIView):
    """
    Public GET by slug (for reading articles) + staff PATCH/DELETE by slug.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantStaffOrAbove()]

    def get_object_by_slug(self, slug):
        try:
            return BlogPost.objects.get(slug=slug, is_published=True)
        except BlogPost.DoesNotExist:
            return None

    @extend_schema(responses={200: BlogPostSerializer})
    def get(self, request, slug, *args, **kwargs):
        post = self.get_object_by_slug(slug)
        if not post:
            return self.error_response("Blog post not found", status_code=status.HTTP_404_NOT_FOUND)
        # Increment views count safely
        BlogPost.objects.filter(pk=post.pk).update(views_count=post.views_count + 1)
        post.refresh_from_db()
        return self.success_response(data=BlogPostSerializer(post).data)

    @extend_schema(request=BlogPostSerializer, responses={200: BlogPostSerializer})
    def patch(self, request, slug, *args, **kwargs):
        try:
            post = BlogPost.objects.get(slug=slug)
        except BlogPost.DoesNotExist:
            return self.error_response("Blog post not found", status_code=status.HTTP_404_NOT_FOUND)
        serializer = BlogPostSerializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(data=serializer.data, message="Blog post updated successfully")

    def delete(self, request, slug, *args, **kwargs):
        try:
            post = BlogPost.objects.get(slug=slug)
        except BlogPost.DoesNotExist:
            return self.error_response("Blog post not found", status_code=status.HTTP_404_NOT_FOUND)
        post.delete()
        return self.success_response(data=None, message="Blog post deleted")


class ManageBlogPostListView(StandardResponseMixin, APIView):
    """
    Staff-only: list ALL blog posts (including drafts) for dashboard content manager.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantStaffOrAbove]

    @extend_schema(responses={200: BlogPostSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        posts = BlogPost.objects.all()
        serializer = BlogPostSerializer(posts, many=True)
        return self.success_response(data=serializer.data)

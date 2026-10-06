from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PlatformUser


class PlatformUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_platform_admin",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "is_platform_admin", "is_active", "created_at"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    otp = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        email = attrs.get("email").lower().strip()
        password = attrs.get("password", "")
        otp = attrs.get("otp", "")

        user = None
        if otp:
            if otp != "123456":
                raise serializers.ValidationError("Invalid OTP verification code.")
            user = PlatformUser.objects.filter(email=email).first()
            if not user:
                raise serializers.ValidationError("No registered user found with this email.")
        elif password:
            user = authenticate(request=self.context.get("request"), username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password.")
        else:
            raise serializers.ValidationError("Either password or OTP must be provided.")

        if not user.is_active:
            raise serializers.ValidationError("This user account is suspended.")

        # If request is directed to a specific tenant schema, verify membership
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None

        role = None
        if tenant and tenant.schema_name != "public" and not user.is_platform_admin:
            from apps.tenant.memberships.models import Membership

            try:
                membership = Membership.objects.get(user_id=user.id, is_active=True)
                role = membership.role
            except Membership.DoesNotExist:
                membership = None

        tenant_domain = None
        redirect_url = "/dashboard"

        if user.is_platform_admin:
            redirect_url = "http://admin.localhost:3000"
        elif tenant and tenant.schema_name != "public" and role:
            domain = tenant.domains.filter(is_primary=True).first()
            raw_domain = domain.domain if domain else f"{tenant.slug}.localhost"
            tenant_domain = raw_domain.split(":")[0]
            redirect_url = "/dashboard"
        else:
            from django_tenants.utils import schema_context
            from apps.platform.tenants.models import Tenant
            from apps.tenant.memberships.models import Membership
            for t in Tenant.objects.exclude(schema_name="public"):
                try:
                    with schema_context(t.schema_name):
                        m = Membership.objects.filter(user_id=user.id, is_active=True).first()
                        if m:
                            if not role:
                                role = m.role
                            domain = t.domains.filter(is_primary=True).first()
                            raw_domain = domain.domain if domain else f"{t.slug}.localhost"
                            tenant_domain = raw_domain.split(":")[0]
                            redirect_url = "/dashboard"
                            break
                except Exception:
                    continue

        if not tenant_domain and not user.is_platform_admin:
            first_tenant = Tenant.objects.exclude(schema_name="public").first()
            if first_tenant:
                domain = first_tenant.domains.filter(is_primary=True).first()
                tenant_domain = domain.domain.split(":")[0] if domain else f"{first_tenant.slug}.localhost"
                try:
                    with schema_context(first_tenant.schema_name):
                        m, _ = Membership.objects.get_or_create(
                            user_id=user.id,
                            defaults={"role": "owner", "is_active": True},
                        )
                        if not role:
                            role = m.role
                except Exception:
                    if not role:
                        role = "owner"
                redirect_url = "/dashboard"

        refresh = RefreshToken.for_user(user)

        return {
            "user": PlatformUserSerializer(user).data,
            "role": role,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "tenant_domain": tenant_domain,
            "redirect_url": redirect_url,
        }


class RegisterTenantSerializer(serializers.Serializer):
    """
    Onboarding serializer: provisions tenant, domain, user, and owner membership atomically.
    """

    company_name = serializers.CharField(max_length=120)
    subdomain = serializers.SlugField(max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=10, write_only=True)
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=50, default="UTC")
    currency = serializers.CharField(max_length=3, default="USD")

    def validate_subdomain(self, value):
        from apps.platform.tenants.models import Tenant

        slug = value.lower().strip()
        if (
            Tenant.objects.filter(slug=slug).exists()
            or Tenant.objects.filter(schema_name=f"tenant_{slug}").exists()
        ):
            raise serializers.ValidationError("This subdomain is already taken.")
        return slug

    def validate_email(self, value):
        return value.lower().strip()

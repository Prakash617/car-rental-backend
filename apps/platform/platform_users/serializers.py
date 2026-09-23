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
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email").lower().strip()
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), username=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")

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
                raise serializers.ValidationError(
                    "You do not possess an active membership with this car rental company."
                ) from None

        refresh = RefreshToken.for_user(user)

        return {
            "user": PlatformUserSerializer(user).data,
            "role": role,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
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

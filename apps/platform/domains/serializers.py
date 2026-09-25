from rest_framework import serializers
from .models import Domain


class DomainSerializer(serializers.ModelSerializer):
    target_cname = serializers.SerializerMethodField()
    ssl_certificate = serializers.SerializerMethodField()

    class Meta:
        model = Domain
        fields = [
            "id",
            "domain",
            "is_primary",
            "is_verified",
            "target_cname",
            "ssl_certificate",
            "created_at",
        ]
        read_only_fields = ["id", "is_primary", "is_verified", "created_at"]

    def get_target_cname(self, obj):
        return "cname.apex-platform.com"

    def get_ssl_certificate(self, obj):
        return {
            "status": "active" if obj.is_verified else "pending",
            "issuer": "Let's Encrypt Authority X3",
            "type": "Auto-renewing TLS 1.3",
        }


class AddCustomDomainSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=253, required=True)

    def validate_domain(self, value):
        domain = value.strip().lower()
        if domain.startswith("http://") or domain.startswith("https://"):
            domain = domain.split("://")[-1]
        domain = domain.split("/")[0].split(":")[0]

        if not domain or len(domain) < 4 or "." not in domain:
            raise serializers.ValidationError("Enter a valid Fully Qualified Domain Name (e.g. rentals.apex.com).")

        if Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"Domain '{domain}' is already registered on this platform.")

        return domain

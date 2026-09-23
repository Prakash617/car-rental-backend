from rest_framework import serializers

from .models import Membership, RoleChoices


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "user_email",
            "user_name",
            "role",
            "is_active",
            "invited_email",
            "invitation_accepted_at",
            "created_at",
        ]
        read_only_fields = ["id", "user_id", "invitation_accepted_at", "created_at"]

    def get_user_email(self, obj):
        user = obj.get_user()
        return user.email if user else obj.invited_email

    def get_user_name(self, obj):
        user = obj.get_user()
        return user.full_name if user else None


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            RoleChoices.ADMIN,
            RoleChoices.MANAGER,
            RoleChoices.STAFF,
            RoleChoices.ACCOUNTANT,
            RoleChoices.VIEWER,
        ]
    )

    def validate_email(self, value):
        from apps.platform.platform_users.models import PlatformUser

        email = value.lower().strip()
        # Check if already a member in this tenant
        existing_user = PlatformUser.objects.filter(email=email).first()
        if (
            existing_user
            and Membership.objects.filter(user_id=existing_user.id, is_active=True).exists()
        ):
            raise serializers.ValidationError(
                "This user is already an active member of this rental company."
            )
        if Membership.objects.filter(invited_email=email, is_active=True).exists():
            raise serializers.ValidationError(
                "An active invitation is already pending for this email."
            )
        return email


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=10, write_only=True)
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)

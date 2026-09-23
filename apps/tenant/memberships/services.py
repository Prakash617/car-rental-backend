import secrets

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.platform.platform_users.models import PlatformUser

from .models import Membership


class MembershipService:
    @classmethod
    def invite_member(cls, email: str, role: str) -> Membership:
        """Invites a staff member to the current tenant company."""
        token = secrets.token_urlsafe(32)
        membership = Membership.objects.create(
            invited_email=email,
            role=role,
            invitation_token=token,
            is_active=True,
        )
        return membership

    @classmethod
    def accept_invitation(
        cls, token: str, password: str, first_name: str, last_name: str
    ) -> tuple[PlatformUser, Membership]:
        """Accepts an invitation, creating or binding the PlatformUser."""
        membership = Membership.objects.filter(invitation_token=token, is_active=True).first()
        if not membership:
            raise ValidationError("Invalid or expired invitation token.")

        email = membership.invited_email.lower().strip()
        user = PlatformUser.objects.filter(email=email).first()

        if not user:
            user = PlatformUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

        membership.user_id = user.id
        membership.invitation_token = None
        membership.invitation_accepted_at = timezone.now()
        membership.save(
            update_fields=["user_id", "invitation_token", "invitation_accepted_at", "updated_at"]
        )

        return user, membership

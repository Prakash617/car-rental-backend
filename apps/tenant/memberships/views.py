from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions.tenant import IsTenantMember, IsTenantOwnerOrAdmin

from .models import Membership
from .serializers import AcceptInviteSerializer, InviteMemberSerializer, MembershipSerializer
from .services import MembershipService


class TeamMemberListView(APIView):
    permission_classes = [IsTenantMember]

    @extend_schema(responses={200: MembershipSerializer(many=True)})
    def get(self, request):
        memberships = Membership.objects.filter(is_active=True)
        serializer = MembershipSerializer(memberships, many=True)
        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )


class InviteMemberView(APIView):
    permission_classes = [IsTenantOwnerOrAdmin]

    @extend_schema(request=InviteMemberSerializer, responses={201: MembershipSerializer})
    def post(self, request):
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = MembershipService.invite_member(
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
        )
        return Response(
            {
                "success": True,
                "data": MembershipSerializer(membership).data,
                "message": "Invitation created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class AcceptInviteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=AcceptInviteSerializer)
    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, membership = MembershipService.accept_invitation(
            token=serializer.validated_data["token"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data["last_name"],
        )
        return Response(
            {
                "success": True,
                "data": {
                    "user_id": str(user.id),
                    "email": user.email,
                    "role": membership.role,
                },
                "message": "Invitation accepted successfully. You may now log in.",
            }
        )

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform.tenants.services import TenantProvisioningService

from .serializers import LoginSerializer, PlatformUserSerializer, RegisterTenantSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: LoginSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "success": True,
                "data": serializer.validated_data,
            }
        )


class RegisterTenantView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterTenantSerializer)
    def post(self, request):
        serializer = RegisterTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = TenantProvisioningService.provision_tenant(serializer.validated_data)

        return Response(
            {
                "success": True,
                "data": {
                    "tenant_id": str(result["tenant"].id),
                    "company_name": result["tenant"].name,
                    "schema_name": result["tenant"].schema_name,
                    "domain": result["domain"].domain,
                    "owner_email": result["user"].email,
                },
                "message": "Tenant company provisioned successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PlatformUserSerializer})
    def get(self, request):
        user_data = PlatformUserSerializer(request.user).data
        tenant = getattr(request, "tenant", None)
        membership = getattr(request, "tenant_membership", None)

        return Response(
            {
                "success": True,
                "data": {
                    "user": user_data,
                    "tenant": {
                        "schema_name": tenant.schema_name if tenant else "public",
                        "name": getattr(tenant, "name", "Platform"),
                    },
                    "role": membership.role if membership else None,
                },
            }
        )

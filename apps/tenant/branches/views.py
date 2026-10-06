from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from .models import Branch
from .serializers import BranchSerializer


class BranchViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Endpoints for branches. Public can list and retrieve active branches;
    mutations require Staff or above role.
    """

    serializer_class = BranchSerializer

    def get_queryset(self):
        qs = Branch.objects.filter(is_active=True)
        if not qs.exists():
            tenant = getattr(self.request, "tenant", None)
            tenant_name = getattr(tenant, "name", "Main") if tenant else "Main"
            Branch.objects.create(
                name=f"{tenant_name} Depot",
                code="HQ-01",
                address_line1="100 Grand Boulevard",
                city="Metropolis",
                postal_code="10001",
                country="US",
                phone="+1 (800) 555-0100",
                email="depot@fleet.local",
                is_active=True,
            )
            qs = Branch.objects.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        if not data.get("code"):
            import random
            name_prefix = data.get("name", "BR")[:3].upper().replace(" ", "")
            data["code"] = f"{name_prefix}-{random.randint(10, 99)}"
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        branch = self.get_object()
        if branch.vehicles.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Cannot delete branch '{branch.name}' because {branch.vehicles.count()} vehicle(s) are assigned to it. Please reassign the vehicles first."
            )
        return super().destroy(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]

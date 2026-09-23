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

    queryset = Branch.objects.filter(is_active=True)
    serializer_class = BranchSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]

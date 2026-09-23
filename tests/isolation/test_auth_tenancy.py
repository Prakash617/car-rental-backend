import pytest
from django_tenants.utils import schema_context

from apps.platform.domains.models import Domain
from apps.platform.platform_users.models import PlatformUser
from apps.platform.tenants.services import TenantProvisioningService
from apps.tenant.memberships.models import Membership, RoleChoices


@pytest.fixture
def multi_tenant_user(db):
    return PlatformUser.objects.create_user(
        email="john.multi@example.com",
        password="SecureMultiPassword123!",
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def tenant_alpha_and_beta_memberships(db, tenant_a, tenant_b, multi_tenant_user):
    # Tenant A: John is Owner
    with schema_context(tenant_a.schema_name):
        Membership.objects.create(
            user_id=multi_tenant_user.id,
            role=RoleChoices.OWNER,
            is_active=True,
        )

    # Tenant B: John is Staff
    with schema_context(tenant_b.schema_name):
        Membership.objects.create(
            user_id=multi_tenant_user.id,
            role=RoleChoices.STAFF,
            is_active=True,
        )

    return multi_tenant_user


@pytest.mark.django_db
class TestAuthenticationAndTenancyIsolation:
    def test_single_user_multiple_tenant_roles(
        self, api_client, tenant_a, tenant_b, tenant_alpha_and_beta_memberships
    ):
        """
        Verifies that a single global user account dynamically resolves
        different roles depending on which tenant domain is accessed.
        """
        user = tenant_alpha_and_beta_memberships

        # 1. Login via Tenant A domain (Host: alpha.platform.local)
        resp_a = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecureMultiPassword123!"},
            HTTP_HOST="alpha.platform.local",
            format="json",
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["success"] is True
        assert resp_a.json()["data"]["role"] == "owner"

        # 2. Login via Tenant B domain (Host: beta.platform.local)
        resp_b = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecureMultiPassword123!"},
            HTTP_HOST="beta.platform.local",
            format="json",
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["success"] is True
        assert resp_b.json()["data"]["role"] == "staff"

    def test_cross_tenant_login_rejection(self, api_client, tenant_a, tenant_b):
        """
        A user who has a membership ONLY in Tenant A must be rejected
        when attempting to authenticate on Tenant B's domain.
        """
        exclusive_user = PlatformUser.objects.create_user(
            email="exclusive.alpha@example.com",
            password="AlphaPassword123!",
            first_name="Alpha",
            last_name="Only",
        )
        with schema_context(tenant_a.schema_name):
            Membership.objects.create(
                user_id=exclusive_user.id,
                role=RoleChoices.STAFF,
                is_active=True,
            )

        # Attempt login on Tenant B
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": exclusive_user.email, "password": "AlphaPassword123!"},
            HTTP_HOST="beta.platform.local",
            format="json",
        )
        assert resp.status_code == 400
        assert resp.json()["success"] is False
        assert "not possess an active membership" in str(resp.json()["error"])

    def test_rbac_role_enforcement_on_team_invite(self, api_client, tenant_a):
        """
        Tests that only Owner/Admin can invite team members;
        Staff role receives 403 Forbidden.
        """
        owner_user = PlatformUser.objects.create_user(
            email="owner@alpha.com",
            password="OwnerPassword123!",
            first_name="Alice",
            last_name="Owner",
        )
        staff_user = PlatformUser.objects.create_user(
            email="staff@alpha.com",
            password="StaffPassword123!",
            first_name="Bob",
            last_name="Staff",
        )

        with schema_context(tenant_a.schema_name):
            Membership.objects.create(user_id=owner_user.id, role=RoleChoices.OWNER)
            Membership.objects.create(user_id=staff_user.id, role=RoleChoices.STAFF)

        # 1. Staff attempts to invite -> 403
        api_client.force_authenticate(user=staff_user)
        resp_staff = api_client.post(
            "/api/v1/team/invite/",
            {"email": "newbie@alpha.com", "role": "viewer"},
            HTTP_HOST="alpha.platform.local",
            format="json",
        )
        assert resp_staff.status_code == 403

        # 2. Owner attempts to invite -> 201 Created
        api_client.force_authenticate(user=owner_user)
        resp_owner = api_client.post(
            "/api/v1/team/invite/",
            {"email": "newbie@alpha.com", "role": "viewer"},
            HTTP_HOST="alpha.platform.local",
            format="json",
        )
        assert resp_owner.status_code == 201
        assert resp_owner.json()["success"] is True
        assert resp_owner.json()["data"]["role"] == "viewer"

    def test_tenant_provisioning_pipeline(self):
        """
        Verifies end-to-end atomic tenant onboarding:
        creates user, tenant schema, domain, and owner membership.
        """
        data = {
            "company_name": "Royal Prestige Cars",
            "subdomain": "royal-prestige",
            "email": "director@royalprestige.com",
            "password": "RoyalSecretPassword999!",
            "first_name": "Charles",
            "last_name": "Windsor",
            "timezone": "Europe/London",
            "currency": "GBP",
        }
        result = TenantProvisioningService.provision_tenant(data)

        tenant = result["tenant"]
        assert tenant.schema_name == "tenant_royal_prestige"
        assert tenant.currency == "GBP"

        # Check domain
        domain = Domain.objects.get(domain="royal-prestige.platform.local")
        assert domain.tenant == tenant

        # Check membership in tenant schema
        with schema_context(tenant.schema_name):
            membership = Membership.objects.get(user_id=result["user"].id)
            assert membership.role == "owner"
            assert membership.is_active is True

    def test_invitation_acceptance_lifecycle(self, api_client, tenant_a):
        """
        Verifies staff invitation creation and acceptance workflow.
        """
        # Create invitation
        with schema_context(tenant_a.schema_name):
            invite = Membership.objects.create(
                invited_email="sarah.invitee@example.com",
                role=RoleChoices.MANAGER,
                invitation_token="test-secret-token-xyz-123",
                is_active=True,
            )

        # Accept invitation
        resp = api_client.post(
            "/api/v1/team/accept-invite/",
            {
                "token": "test-secret-token-xyz-123",
                "password": "SarahPasswordSecure2026!",
                "first_name": "Sarah",
                "last_name": "Connor",
            },
            HTTP_HOST="alpha.platform.local",
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify user now created in public schema and membership linked
        new_user = PlatformUser.objects.get(email="sarah.invitee@example.com")
        assert new_user.first_name == "Sarah"

        with schema_context(tenant_a.schema_name):
            updated_membership = Membership.objects.get(id=invite.id)
            assert updated_membership.user_id == new_user.id
            assert updated_membership.invitation_token is None
            assert updated_membership.invitation_accepted_at is not None

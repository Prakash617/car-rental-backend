from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenant.maintenance.views import (
    FleetHealthOverviewView,
    MaintenanceViewSet,
    ServiceIntervalViewSet,
    TelemetryViewSet,
    VehicleInspectionViewSet,
)

router = DefaultRouter()
router.register(r"records", MaintenanceViewSet, basename="maintenance-record")
router.register(r"inspections", VehicleInspectionViewSet, basename="vehicle-inspection")
router.register(r"telemetry", TelemetryViewSet, basename="vehicle-telemetry")
router.register(r"intervals", ServiceIntervalViewSet, basename="service-interval")

urlpatterns = [
    path("overview/", FleetHealthOverviewView.as_view(), name="fleet-health-overview"),
    path("", include(router.urls)),
]

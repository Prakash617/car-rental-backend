from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenant.notifications.views import NotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]

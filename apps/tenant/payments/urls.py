from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenant.payments.views import (
    CheckoutSessionView,
    ManualPaymentView,
    PaymentViewSet,
    WebhookIngressView,
)

router = DefaultRouter()
router.register(r"transactions", PaymentViewSet, basename="payment-transaction")

urlpatterns = [
    path("checkout/", CheckoutSessionView.as_view(), name="payment-checkout"),
    path("manual/", ManualPaymentView.as_view(), name="payment-manual"),
    path("webhooks/<str:provider>/", WebhookIngressView.as_view(), name="payment-webhook"),
    path("", include(router.urls)),
]

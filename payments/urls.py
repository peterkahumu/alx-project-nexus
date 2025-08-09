# payments/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InitiatePaymentView, PaymentView, ProviderVerifyView

router = DefaultRouter()
router.register(r"", PaymentView, basename="payments")

urlpatterns = [
    # Start a payment for a given order
    path(
        "initiate/<uuid:order_id>/",
        InitiatePaymentView.as_view(),
        name="initiate-payment",
    ),
    path(
        "verify/<str:provider>/", ProviderVerifyView.as_view(), name="provider-verify"
    ),
    path("", include(router.urls)),
]

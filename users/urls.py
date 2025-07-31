from django.urls import path

from .views import RegisterAPIView, ResendActivationEmailView, confirmEmailView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("confirm-email/", confirmEmailView.as_view(), name="confirm-email"),
    path(
        "resend-activation-email/",
        ResendActivationEmailView.as_view(),
        name="resend-activation",
    ),
]

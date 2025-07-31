from django.urls import path

from .views import PasswordResetConfirmView  # noqa
from .views import PasswordResetRequestView  # noqa
from .views import ConfirmEmailView, RegisterAPIView, ResendActivationEmailView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("confirm-email/", ConfirmEmailView.as_view(), name="confirm-email"),
    path(
        "resend-activation-email/",
        ResendActivationEmailView.as_view(),
        name="resend-activation",
    ),
    # Password reset
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset-confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]

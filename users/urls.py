from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ConfirmEmailView,
    CustomLoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterAPIView,
    ResendActivationEmailView,
)

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
    # login
    path("login/", CustomLoginView.as_view(), name="login"),
    path("refresh-session/", TokenRefreshView.as_view(), name="refresh-token"),
]

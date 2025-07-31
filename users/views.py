from typing import List

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer

User = get_user_model()


class RegisterAPIView(generics.CreateAPIView):
    """User registration endpoint"""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"success": "User registered successfully. Please log in"},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class confirmEmailView(APIView):
    """Confirm user email using uid and token from URL parameters."""

    def get(self, request):
        """Activate user using link sent to their email"""
        uid = request.GET.get("uid")
        token = request.GET.get("token")

        if not uid or not token:
            return Response(
                {"error": "Missing uid or token"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # decode the user id
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)

            if default_token_generator.check_token(user, token):
                # activate the user
                user.is_active = True
                user.save()
                return Response(
                    {"success": "Email confirmed. Please log in."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Invalid or expired token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid confirmation link"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ResendActivationEmailView(APIView):
    """Resend activation email for unverified accounts"""

    permission_classes: List[BasePermission] = []

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)

            if user.is_active:
                return Response(
                    {"error": "Account already activated. Please log in."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            confirm_url = f"{request.build_absolute_uri('/')[:-1]}/api/users/confirm-email/?uid={uid}&token={token}"  # noqa

            from .tasks import send_activation_email

            send_activation_email.delay(user.email, confirm_url)

            return Response(
                {
                    "success": "If an account with that email exists and is unverified, a link will be sent"  # noqa
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            # do not reveal the user does not exist
            return Response(
                {
                    "success": "If an account with that email exists and is unverified, a link will be sent"  # noqa
                },
                status=status.HTTP_200_OK,
            )

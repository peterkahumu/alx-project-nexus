from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status
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

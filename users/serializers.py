from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Custom user registration field."""

    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
            "phone",
            "role",
            "profile_image",
        ]
        extra_kwargs = {
            "role": {"required": False},
            "profile_image": {"required": False},
        }

    def validate_role(self, value):
        """convert role value to lowercase and trailing or preceeding spaces"""
        return value.strip().lower()

    def validate(self, attrs):
        """Validate submitted user information."""
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"error": "Passwords do not match."})

        if len(attrs["password"]) < 6:
            raise serializers.ValidationError(
                {"error": "Password must be greater than 6 characters."}
            )

        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError(
                {"error": "User with that email already exists."}
            )

        return attrs

    def create(self, validated_data):
        """Save the user to the Database"""
        validated_data.pop("confirm_password")

        role = validated_data.pop("role", None)
        if role:
            user = User.objects.create_user(
                **validated_data, role=role, is_active=False
            )
        else:
            user = User.objects.create_user(**validated_data, is_active=False)

        if role and role == "admin":
            user.is_staff = True
            user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate email format"""
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset"""

    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        min_length=6,
        required=True,
        help_text="Password must be at least 6 characters long",
    )
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"error": "Passwords do not match"})

        if len(attrs["new_password"]) < 6:
            raise serializers.ValidationError(
                {"error": "Password must be at least 6 characters long"}
            )

        return attrs

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

        if User.objects.filter(username=attrs["username"]).exists():
            raise serializers.ValidationError(
                {"error": "Username already taken. Please use another."}
            )

        return attrs

    def create(self, validated_data):
        """Save the user to the Database"""
        validated_data.pop("confirm_password")

        user = User.objects.create_user(**validated_data)

        if validated_data["role"] and validated_data["role"] == "admin":
            user.is_staff = True
            user.save()

        return user

import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image
from rest_framework import serializers, status
from rest_framework.test import APIClient

from .models import User
from .serializers import (
    CustomLoginSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
)
from .tasks import send_password_reset_email


class TestUserModel(TestCase):
    """Test User model functionality"""

    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        }

    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.user_id)
        self.assertIsNotNone(user.created_at)

    def test_create_inactive_user(self):
        """Test creating user as inactive for email verification"""
        user_data = self.user_data.copy()
        user_data["is_active"] = False
        user = User.objects.create_user(**user_data)
        self.assertFalse(user.is_active)

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="admin",
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, "admin")

    def test_soft_delete(self):
        user = User.objects.create_user(**self.user_data)
        user.delete()
        self.assertIsNotNone(user.deleted_at)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(User.all_objects.count(), 1)

    def test_soft_deleted_user_not_in_queryset(self):
        user = User.objects.create_user(**self.user_data)
        user.delete()
        self.assertFalse(User.objects.filter(username="testuser").exists())
        self.assertTrue(User.all_objects.filter(username="testuser").exists())

    def test_create_user_with_missing_fields(self):
        with self.assertRaises(TypeError):
            User.objects.create_user(username="incomplete")

    def test_create_user_with_blank_email(self):
        """Ensure creating a user without email raises ValueError"""
        with self.assertRaisesMessage(ValueError, "Email is required"):
            User.objects.create_user(
                username="blankemail",
                email="",
                first_name="Blank",
                last_name="Email",
                password="pass123",
            )

    def test_create_superuser_sets_admin_role(self):
        admin = User.objects.create_superuser(
            username="superadmin", email="admin@example.com", password="adminpass123"
        )
        self.assertEqual(admin.role, "admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class TestRegisterSerializer(TestCase):
    """Test registration serializer validation"""

    def setUp(self):
        self.valid_data = {
            "username": "newuser",
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "testpass123",
            "confirm_password": "testpass123",
            "phone": "+254712345678",
        }

    def test_valid_registration(self):
        serializer = RegisterSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

    def test_password_mismatch(self):
        invalid_data = self.valid_data.copy()
        invalid_data["confirm_password"] = "wrongpassword"
        serializer = RegisterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("error", serializer.errors)

    def test_weak_password(self):
        invalid_data = self.valid_data.copy()
        invalid_data["password"] = "123"
        invalid_data["confirm_password"] = "123"
        serializer = RegisterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("error", serializer.errors)

    def test_duplicate_email(self):
        User.objects.create_user(
            username="existing",
            email="new@example.com",
            first_name="Existing",
            last_name="User",
            password="existing123",
        )
        serializer = RegisterSerializer(data=self.valid_data)
        self.assertFalse(serializer.is_valid())
        # The serializer returns validation error with "email" key for duplicate email
        self.assertIn("email", serializer.errors)

    def test_duplicate_username(self):
        User.objects.create_user(
            username="newuser",
            email="existing@example.com",
            first_name="Existing",
            last_name="User",
            password="existing123",
        )
        serializer = RegisterSerializer(data=self.valid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_role_normalization(self):
        data = self.valid_data.copy()
        data["role"] = "  ADMIN  "
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["role"], "admin")

    def test_profile_image_upload(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
            image = Image.new("RGB", (100, 100))
            image.save(temp_file, format="JPEG")
            temp_file.seek(0)
            uploaded = SimpleUploadedFile(
                name="test.jpg", content=temp_file.read(), content_type="image/jpeg"
            )
            data = self.valid_data.copy()
            data["profile_image"] = uploaded
            serializer = RegisterSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    def test_create_admin_user(self):
        data = self.valid_data.copy()
        data["role"] = "admin"
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "admin")
        self.assertFalse(user.is_active)  # Should be inactive for email verification

    def test_create_user_is_inactive_by_default(self):
        """Test that newly created users are inactive for email verification"""
        serializer = RegisterSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertFalse(user.is_active)

    def test_invalid_email_format(self):
        data = self.valid_data.copy()
        data["email"] = "bad-email-format"
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_missing_username(self):
        data = self.valid_data.copy()
        del data["username"]
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_long_username(self):
        data = self.valid_data.copy()
        data["username"] = "a" * 101
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_invalid_profile_image_type(self):
        bad_file = SimpleUploadedFile(
            "test.txt", b"badcontent", content_type="text/plain"
        )
        data = self.valid_data.copy()
        data["profile_image"] = bad_file
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("profile_image", serializer.errors)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,  # Execute tasks synchronously for testing
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",  # Use in-memory email backend
)
class TestRegistrationWithEmailVerification(TestCase):
    """Test registration API endpoint with email verification"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/register/"
        self.valid_payload = {
            "username": "apiuser",
            "email": "api@example.com",
            "first_name": "API",
            "last_name": "User",
            "password": "apipass123",
            "confirm_password": "apipass123",
        }

    def test_successful_registration_sends_email(self):
        """Test that registration creates inactive user and sends email"""
        with patch("users.tasks.send_activation_email.delay") as mock_task:
            response = self.client.post(
                self.url, data=self.valid_payload, format="json"
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(
                response.data["success"], "User registered successfully. Please log in"
            )

            # User should exist but be inactive
            user = User.objects.get(username="apiuser")
            self.assertFalse(user.is_active)

            # Email task should be called
            mock_task.assert_called_once()
            args = mock_task.call_args[0]
            self.assertEqual(args[0], "api@example.com")  # Email
            self.assertIn("confirm-email", args[1])  # URL contains confirmation link

    def test_registration_creates_inactive_user(self):
        """Test that registered users are inactive by default"""
        response = self.client.post(self.url, data=self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="apiuser")
        self.assertFalse(user.is_active)

    def test_invalid_registration(self):
        invalid_payload = self.valid_payload.copy()
        invalid_payload["confirm_password"] = "wrongpassword"
        response = self.client.post(self.url, data=invalid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_missing_required_fields(self):
        incomplete_payload = {
            "username": "incomplete",
            "password": "test123",
            "confirm_password": "test123",
        }
        response = self.client.post(self.url, data=incomplete_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertIn("first_name", response.data)
        self.assertIn("last_name", response.data)

    def test_admin_registration(self):
        admin_payload = self.valid_payload.copy()
        admin_payload["role"] = "admin"
        response = self.client.post(self.url, data=admin_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="apiuser")
        self.assertTrue(user.is_staff)  # Should be staff for admin role
        self.assertEqual(user.role, "admin")
        self.assertFalse(user.is_active)  # Still inactive for email verification

    def test_register_with_extra_fields(self):
        payload = self.valid_payload.copy()
        payload["extra_field"] = "hacker"
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_with_empty_payload(self):
        response = self.client.post(self.url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)

    def test_register_twice_with_same_data(self):
        self.client.post(self.url, data=self.valid_payload, format="json")
        response = self.client.post(self.url, data=self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should have validation errors for duplicate fields
        self.assertTrue("username" in response.data or "email" in response.data)


class TestEmailConfirmationView(TestCase):
    """Test email confirmation functionality"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/confirm-email/"
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
            is_active=False,
        )

    def test_successful_email_confirmation(self):
        """Test successful email confirmation activates user"""
        # Generate valid uid and token
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.get(f"{self.url}?uid={uid}&token={token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], "Email confirmed. Please log in.")

        # User should now be active
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_missing_uid(self):
        """Test confirmation fails when uid is missing"""
        token = default_token_generator.make_token(self.user)
        response = self.client.get(f"{self.url}?token={token}")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Missing uid or token")

    def test_missing_token(self):
        """Test confirmation fails when token is missing"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(f"{self.url}?uid={uid}")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Missing uid or token")

    def test_invalid_uid(self):
        """Test confirmation fails with invalid uid"""
        token = default_token_generator.make_token(self.user)
        response = self.client.get(f"{self.url}?uid=invalid&token={token}")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid confirmation link")

    def test_invalid_token(self):
        """Test confirmation fails with invalid token"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(f"{self.url}?uid={uid}&token=invalid")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid or expired token")

    def test_nonexistent_user(self):
        """Test confirmation fails for non-existent user"""
        fake_uuid = uuid.uuid4()
        uid = urlsafe_base64_encode(force_bytes(str(fake_uuid)))  # Non-existent user ID
        token = "sometoken"
        response = self.client.get(f"{self.url}?uid={uid}&token={token}")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid confirmation link")

    def test_already_active_user_confirmation(self):
        """Test confirming email for already active user"""
        # Make user active first
        self.user.is_active = True
        self.user.save()

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.get(f"{self.url}?uid={uid}&token={token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], "Email confirmed. Please log in.")

    def test_expired_token(self):
        """Test confirmation fails with expired token"""
        # Create an old token by manipulating the user's last_login
        from datetime import timedelta

        from django.utils import timezone

        # Make the user look like it was created long ago
        old_time = timezone.now() - timedelta(days=10)
        User.objects.filter(pk=self.user.pk).update(
            last_login=old_time, date_joined=old_time
        )

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        # Generate token with old user state
        old_user = User.objects.get(pk=self.user.pk)
        token = default_token_generator.make_token(old_user)

        # Now update user to current time (simulating time passing)
        self.user.last_login = timezone.now()
        self.user.save()

        response = self.client.get(f"{self.url}?uid={uid}&token={token}")

        # Token should be invalid due to time difference
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid or expired token")


class TestEmailVerificationSignals(TestCase):
    """Test email verification signals"""

    @patch("users.tasks.send_activation_email.delay")
    def test_signal_triggered_on_user_creation(self, mock_task):
        """Test that signal is triggered when user is created"""
        User.objects.create_user(
            username="signaltest",
            email="signal@example.com",
            first_name="Signal",
            last_name="Test",
            password="testpass123",
            is_active=False,
        )

        # Signal should trigger email task
        mock_task.assert_called_once()
        args = mock_task.call_args[0]
        self.assertEqual(args[0], "signal@example.com")
        self.assertIn("confirm-email", args[1])

    @patch("users.tasks.send_activation_email.delay")
    def test_signal_not_triggered_for_active_user(self, mock_task):
        """Test that signal is not triggered for active users"""
        User.objects.create_user(
            username="activeuser",
            email="active@example.com",
            first_name="Active",
            last_name="User",
            password="testpass123",
            is_active=True,
        )

        # Signal should not trigger email task for active users
        mock_task.assert_not_called()

    @patch("users.tasks.send_activation_email.delay")
    def test_signal_not_triggered_on_user_update(self, mock_task):
        """Test that signal is not triggered when existing user is updated"""
        user = User.objects.create_user(
            username="updatetest",
            email="update@example.com",
            first_name="Update",
            last_name="Test",
            password="testpass123",
            is_active=False,
        )

        # Reset mock after user creation
        mock_task.reset_mock()

        # Update user
        user.first_name = "Updated"
        user.save()

        # Signal should not trigger on update
        mock_task.assert_not_called()


class TestUserStr(TestCase):
    def test_user_str(self):
        user = User.objects.create_user(
            username="strtest",
            email="str@example.com",
            first_name="Str",
            last_name="Test",
            password="strpass123",
        )
        self.assertEqual(str(user), "strtest")


class TestUUIDField(TestCase):
    def test_uuid_generation(self):
        user = User.objects.create_user(
            username="uuidtest",
            email="uuid@example.com",
            first_name="UUID",
            last_name="Test",
            password="uuidpass123",
        )
        self.assertIsNotNone(user.user_id)
        try:
            uuid.UUID(str(user.user_id))
        except ValueError:
            self.fail("UUID field doesn't contain valid UUID")


class TestSecureTokenGeneration(TestCase):
    """Test that email confirmation tokens are secure and don't expose email"""

    def test_token_does_not_contain_email(self):
        """Test that generated tokens don't contain user email"""
        user = User.objects.create_user(
            username="tokentest",
            email="token@example.com",
            first_name="Token",
            last_name="Test",
            password="testpass123",
            is_active=False,
        )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Token should not contain email
        self.assertNotIn("token@example.com", token)
        self.assertNotIn("token", token.lower())

        # UID should not contain email (it's base64 encoded user ID)
        self.assertNotIn("token@example.com", uid)

    def test_different_users_generate_different_tokens(self):
        """Test that different users generate different tokens"""
        user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            first_name="User",
            last_name="One",
            password="testpass123",
            is_active=False,
        )

        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            first_name="User",
            last_name="Two",
            password="testpass123",
            is_active=False,
        )

        token1 = default_token_generator.make_token(user1)
        token2 = default_token_generator.make_token(user2)

        self.assertNotEqual(token1, token2)

    def test_token_is_user_specific(self):
        """Test that tokens are specific to users"""
        user1 = User.objects.create_user(
            username="specific1",
            email="specific1@example.com",
            first_name="Specific",
            last_name="One",
            password="testpass123",
            is_active=False,
        )

        user2 = User.objects.create_user(
            username="specific2",
            email="specific2@example.com",
            first_name="Specific",
            last_name="Two",
            password="testpass123",
            is_active=False,
        )

        token1 = default_token_generator.make_token(user1)

        # Token for user1 should not work for user2
        self.assertFalse(default_token_generator.check_token(user2, token1))
        # But should work for user1
        self.assertTrue(default_token_generator.check_token(user1, token1))


class TestResendActivationEmail(TestCase):
    """Test resend activation email functionality"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/resend-activation-email/"
        self.inactive_user = User.objects.create_user(
            username="inactive",
            email="inactive@example.com",
            first_name="Inactive",
            last_name="User",
            password="password123",
            is_active=False,
        )
        self.active_user = User.objects.create_user(
            username="active",
            email="active@example.com",
            first_name="Active",
            last_name="User",
            password="password123",
            is_active=True,
        )

    @patch("users.tasks.send_activation_email.delay")
    def test_successful_resend_activation_email(self, mock_task):
        """Test successful resend activation email"""
        response = self.client.post(
            self.url, {"email": "inactive@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("If an account with that email exists", response.data["success"])

        # Check that email task was called
        mock_task.assert_called_once()

    def test_resend_activation_email_already_active(self):
        """Test resend activation email for already active user"""
        response = self.client.post(
            self.url, {"email": "active@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], "Account already activated. Please log in."
        )

    def test_resend_activation_email_nonexistent_user(self):
        """Test resend activation email for non-existent user"""
        response = self.client.post(
            self.url, {"email": "nonexistent@example.com"}, format="json"
        )

        # Should return generic message for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("If an account with that email exists", response.data["success"])

    def test_resend_activation_email_missing_email(self):
        """Test resend activation email without email"""
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Email is required.")


class TestPasswordResetRequest(TestCase):
    """Test password reset request functionality"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/password-reset/"
        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            first_name="Reset",
            last_name="User",
            password="oldpassword123",
            is_active=True,
        )

    @patch("users.tasks.send_password_reset_email.delay")
    def test_successful_password_reset_request(self, mock_task):
        """Test successful password reset request"""
        response = self.client.post(
            self.url, {"email": "reset@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sent password reset instructions", response.data["success"])

        # Check that email task was called
        mock_task.assert_called_once()
        args = mock_task.call_args[0]
        self.assertEqual(args[0], "reset@example.com")  # Email
        self.assertIn("password-reset-confirm", args[1])  # Reset URL
        self.assertEqual(args[2], "Reset")  # First name

    def test_password_reset_request_nonexistent_email(self):
        """Test password reset request for non-existent email"""
        response = self.client.post(
            self.url, {"email": "nonexistent@example.com"}, format="json"
        )

        # Should return same message for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sent password reset instructions", response.data["success"])

    def test_password_reset_request_inactive_user(self):
        """Test password reset request for inactive user"""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.url, {"email": "reset@example.com"}, format="json"
        )

        # Should return same message for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sent password reset instructions", response.data["success"])

    def test_password_reset_request_invalid_email(self):
        """Test password reset request with invalid email"""
        response = self.client.post(self.url, {"email": "invalid-email"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_password_reset_request_missing_email(self):
        """Test password reset request without email"""
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    @patch("users.tasks.send_mail")
    def test_send_password_reset_email(self, mock_send_mail):
        send_password_reset_email("test@example.com", "http://reset.link", "Peter")
        mock_send_mail.assert_called_once()
        args = mock_send_mail.call_args[0]
        assert "Hi Peter" in args[1]  # message
        assert "Reset your password" in args[0]  # subject
        assert "http://reset.link" in args[1]


class TestPasswordResetConfirm(TestCase):
    """Test password reset confirmation functionality"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/password-reset-confirm/"
        self.user = User.objects.create_user(
            username="confirmuser",
            email="confirm@example.com",
            first_name="Confirm",
            last_name="User",
            password="oldpassword123",
            is_active=True,
        )

    def test_successful_password_reset_confirm(self):
        """Test successful password reset confirmation"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            self.url,
            {
                "uid": uid,
                "token": token,
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Password has been reset successfully", response.data["success"])

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword123"))
        self.assertFalse(self.user.check_password("oldpassword123"))

    def test_password_reset_confirm_password_mismatch(self):
        """Test password reset with mismatched passwords"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            self.url,
            {
                "uid": uid,
                "token": token,
                "new_password": "newpassword123",
                "confirm_password": "differentpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset with invalid token"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            self.url,
            {
                "uid": uid,
                "token": "invalid-token",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid or expired token")

    def test_password_reset_confirm_invalid_uid(self):
        """Test password reset with invalid uid"""
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            self.url,
            {
                "uid": "invalid-uid",
                "token": token,
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid reset link")

    def test_password_reset_confirm_nonexistent_user(self):
        """Test password reset for non-existent user"""
        fake_uuid = uuid.uuid4()
        uid = urlsafe_base64_encode(force_bytes(fake_uuid))
        token = "some-token"

        response = self.client.post(
            self.url,
            {
                "uid": uid,
                "token": token,
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid reset link")

    def test_password_reset_confirm_inactive_user(self):
        """Test password reset for inactive user"""
        self.user.is_active = False
        self.user.save()

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            self.url,
            {
                "uid": uid,
                "token": token,
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid reset link")


def test_password_too_short_serializer():
    data = {
        "uid": "test",
        "token": "fake",
        "new_password": "123",
        "confirm_password": "123",
    }
    serializer = PasswordResetConfirmSerializer(data=data)
    assert not serializer.is_valid()
    assert "Ensure this field has at least 6 characters." in str(serializer.errors)


class TestLoginSerializer(TestCase):
    """Test the custom login serializer functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
            is_active=True,
        )
        self.inactive_user = User.objects.create_user(
            username="inactive",
            email="inactive@example.com",
            first_name="Inactive",
            last_name="User",
            password="inactive123",
            is_active=False,
        )

    def test_successful_login_with_username(self):
        """Test successful login using username"""
        data = {"username": "testuser", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        result = serializer.validate(data)
        self.assertIn("access", result)
        self.assertIn("refresh", result)
        self.assertEqual(result["username"], "testuser")

    def test_successful_login_with_email(self):
        """Test successful login using email"""
        data = {"username": "test@example.com", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        result = serializer.validate(data)
        self.assertIn("access", result)
        self.assertIn("refresh", result)
        self.assertEqual(result["username"], "testuser")

    def test_login_case_insensitive(self):
        """Test login is case insensitive for username/email"""
        # Test uppercase email
        data = {"username": "TEST@EXAMPLE.COM", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Test mixed case username
        data = {"username": "TestUser", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        # Wrong password
        data = {"username": "testuser", "password": "wrongpassword"}
        serializer = CustomLoginSerializer(data=data)
        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate(data)
        self.assertIn("Invalid credentials", str(context.exception))

        # Nonexistent user
        data = {"username": "nonexistent", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate(data)
        self.assertIn("Invalid credentials", str(context.exception))

    def test_inactive_user_login(self):
        """Test login attempt for inactive user"""
        data = {"username": "inactive", "password": "inactive123"}
        serializer = CustomLoginSerializer(data=data)
        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate(data)
        self.assertIn("Account is not active", str(context.exception))

    def test_missing_username(self):
        """Test login with missing username"""
        data = {"password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_missing_password(self):
        """Test login with missing password"""
        data = {"username": "testuser"}
        serializer = CustomLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_empty_username(self):
        """Test login with empty username"""
        data = {"username": "", "password": "testpass123"}
        serializer = CustomLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_empty_password(self):
        """Test login with empty password"""
        data = {"username": "testuser", "password": ""}
        serializer = CustomLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)


class TestLoginView(TestCase):
    """Test the login API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/users/login/"
        self.user = User.objects.create_user(
            username="loginuser",
            email="login@example.com",
            first_name="Login",
            last_name="User",
            password="loginpass123",
            is_active=True,
        )
        self.inactive_user = User.objects.create_user(
            username="inactivelogin",
            email="inactive@example.com",
            first_name="Inactive",
            last_name="Login",
            password="inactive123",
            is_active=False,
        )

    def test_successful_login_with_username(self):
        """Test successful login using username"""
        response = self.client.post(
            self.url,
            {"username": "loginuser", "password": "loginpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["username"], "loginuser")

    def test_successful_login_with_email(self):
        """Test successful login using email"""
        response = self.client.post(
            self.url,
            {"username": "login@example.com", "password": "loginpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["username"], "loginuser")

    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            self.url,
            {"username": "loginuser", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_inactive_user_login(self):
        """Test login attempt for inactive user"""
        response = self.client.post(
            self.url,
            {"username": "inactivelogin", "password": "inactive123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Account is not active", str(response.data))

    def test_missing_credentials(self):
        """Test login with missing credentials"""
        # Missing username
        response = self.client.post(
            self.url,
            {"password": "loginpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

        # Missing password
        response = self.client.post(
            self.url,
            {"username": "loginuser"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_empty_credentials(self):
        """Test login with empty credentials"""
        # Empty username
        response = self.client.post(
            self.url,
            {"username": "", "password": "loginpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

        # Empty password
        response = self.client.post(
            self.url,
            {"username": "loginuser", "password": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)


class TestUserRoleBasedAccess(TestCase):
    """Test role-based access control functionality"""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/users/login/"

        # Create users with different roles
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="customer123",
            role="customer",
            is_active=True,
        )

        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="admin",
            is_active=True,
        )

    def test_role_in_login_response(self):
        """Test that role is included in login response"""
        # Test customer role
        response = self.client.post(
            self.login_url,
            {"username": "customer", "password": "customer123"},
            format="json",
        )
        self.assertEqual(response.data["role"], "customer")

        # Test admin role
        response = self.client.post(
            self.login_url,
            {"username": "admin", "password": "admin123"},
            format="json",
        )
        self.assertEqual(response.data["role"], "admin")

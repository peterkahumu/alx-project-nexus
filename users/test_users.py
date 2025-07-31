import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from .models import User
from .serializers import RegisterSerializer


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
        self.assertIsNotNone(user.uuid)
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
        uid = urlsafe_base64_encode(force_bytes(99999))  # Non-existent user ID
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
        self.assertIsNotNone(user.uuid)
        try:
            uuid.UUID(str(user.uuid))
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

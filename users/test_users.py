import tempfile
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
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


class TestRegisterAPIView(TestCase):
    """Test registration API endpoint"""

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

    def test_successful_registration(self):
        response = self.client.post(self.url, data=self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["success"], "User registered successfully. Please log in"
        )
        self.assertTrue(User.objects.filter(username="apiuser").exists())

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
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "admin")

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
        self.assertIn("username", response.data)


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

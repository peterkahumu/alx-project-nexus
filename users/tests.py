import tempfile
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from .models import User
from .serializers import RegisterSerializer


class TestUserMode(TestCase):
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
        """Test creating a regular user"""
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.uuid)
        self.assertIsNotNone(user.created_at)

    def test_create_superuser(self):
        """Test creating a superuser"""
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
        """Test soft deletion functionality"""
        user = User.objects.create_user(**self.user_data)
        user.delete()

        self.assertIsNotNone(user.deleted_at)
        self.assertEqual(User.objects.count(), 1)


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
        """Test valid registration data"""
        serializer = RegisterSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

    def test_password_mismatch(self):
        """Test password confirmation validation"""
        invalid_data = self.valid_data.copy()
        invalid_data["confirm_password"] = "wrongpassword"

        serializer = RegisterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("error", serializer.errors)
        self.assertEqual(serializer.errors["error"][0], "Passwords do not match.")

    def test_weak_password(self):
        """Test password strength validation"""
        invalid_data = self.valid_data.copy()
        invalid_data["password"] = "123"
        invalid_data["confirm_password"] = "123"

        serializer = RegisterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("error", serializer.errors)
        self.assertEqual(
            serializer.errors["error"][0], "Password must be greater than 6 characters."
        )

    def test_duplicate_email(self):
        """Test duplicate email validation"""
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
        self.assertEqual(
            serializer.errors["email"][0], "user with this email already exists."
        )

    def test_duplicate_username(self):
        """Test duplicate username validation"""
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
        self.assertEqual(
            serializer.errors["username"][0], "user with this username already exists."
        )

    def test_role_normalization(self):
        """Test role field normalization"""
        data = self.valid_data.copy()
        data["role"] = "  ADMIN  "

        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["role"], "admin")

    def test_profile_image_upload(self):
        """Test profile image upload validation"""
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
        """Test admin user creation through serializer"""
        data = self.valid_data.copy()
        data["role"] = "admin"

        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        user = serializer.save()
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "admin")


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
        """Test successful user registration"""
        response = self.client.post(self.url, data=self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["success"], "User registered successfully. Please log in"
        )
        self.assertTrue(User.objects.filter(username="apiuser").exists())

    def test_invalid_registration(self):
        """Test registration with invalid data"""
        invalid_payload = self.valid_payload.copy()
        invalid_payload["confirm_password"] = "wrongpassword"

        response = self.client.post(self.url, data=invalid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_missing_required_fields(self):
        """Test registration with missing required fields"""
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
        """Test admin user registration"""
        admin_payload = self.valid_payload.copy()
        admin_payload["role"] = "admin"

        response = self.client.post(self.url, data=admin_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="apiuser")
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "admin")


class TestUserStr(TestCase):
    """Test user string representation"""

    def test_user_str(self):
        """Test __str__ method"""
        user = User.objects.create_user(
            username="strtest",
            email="str@example.com",
            first_name="Str",
            last_name="Test",
            password="strpass123",
        )

        self.assertEqual(str(user), "strtest")


class TestUUIDField(TestCase):
    """Test UUID field functionality"""

    def test_uuid_generation(self):
        """Test automatic UUID generation"""
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

"""
Comprehensive unit tests for products functionality covering models, serializers, and views.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Product
from products.serializers import CategorySerializer, ProductSerializer

User = get_user_model()


class CategoryModelTests(TestCase):
    """Test cases for Category model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="adminpass123",
            role="admin",
            is_staff=True,
        )

    def test_category_creation_with_all_fields(self):
        """Test creating category with all fields"""
        category = Category.objects.create(
            name="Test Category", description="Test description", created_by=self.user
        )

        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.description, "Test description")
        self.assertEqual(category.slug, "test-category")
        self.assertEqual(category.created_by, self.user)
        self.assertTrue(category.is_active)
        self.assertIsInstance(category.category_id, uuid.UUID)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)

    def test_category_creation_minimal_fields(self):
        """Test creating category with only required fields"""
        category = Category.objects.create(
            name="Minimal Category", created_by=self.user
        )

        self.assertEqual(category.name, "Minimal Category")
        self.assertEqual(category.slug, "minimal-category")
        self.assertIsNone(category.description)
        self.assertFalse(category.category_image)

    def test_category_slug_generation(self):
        """Test automatic slug generation"""
        category = Category.objects.create(
            name="Complex Category Name!@#", created_by=self.user
        )

        self.assertEqual(category.slug, "complex-category-name")

    def test_category_custom_slug(self):
        """Test category with custom slug"""
        category = Category.objects.create(
            name="Test Category", slug="custom-slug", created_by=self.user
        )

        self.assertEqual(category.slug, "custom-slug")

    def test_category_name_uniqueness(self):
        """Test that category names must be unique"""
        Category.objects.create(name="Unique Category", created_by=self.user)

        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Unique Category", created_by=self.admin_user)

    def test_category_slug_uniqueness(self):
        """Test that category slugs must be unique"""
        Category.objects.create(
            name="First Category", slug="unique-slug", created_by=self.user
        )

        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name="Second Category", slug="unique-slug", created_by=self.admin_user
            )

    def test_category_str_method(self):
        """Test category string representation"""
        category = Category.objects.create(name="Test Category", created_by=self.user)

        self.assertEqual(str(category), "Test Category")

    def test_category_with_image(self):
        """Test category creation with image"""
        image = SimpleUploadedFile(
            name="test_image.jpg",
            content=b"fake image content",
            content_type="image/jpeg",
        )

        category = Category.objects.create(
            name="Image Category", category_image=image, created_by=self.user
        )

        self.assertIsNotNone(category.category_image)


class ProductModelTests(TestCase):
    """Test cases for Product model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="adminpass123",
            role="admin",
        )
        self.category = Category.objects.create(
            name="Test Category", created_by=self.user
        )

    def test_product_creation_with_all_fields(self):
        """Test creating product with all fields"""
        product = Product.objects.create(
            name="Test Product",
            description="Test description",
            unit_price=Decimal("99.99"),
            original_price=Decimal("149.99"),
            in_stock=100,
            min_order_quantity=1,
            max_order_quantity=50,
            featured=True,
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.name, "Test Product")
        self.assertEqual(product.description, "Test description")
        self.assertEqual(product.unit_price, Decimal("99.99"))
        self.assertEqual(product.original_price, Decimal("149.99"))
        self.assertEqual(product.in_stock, 100)
        self.assertEqual(product.min_order_quantity, 1)
        self.assertEqual(product.max_order_quantity, 50)
        self.assertTrue(product.featured)
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.created_by, self.user)
        self.assertEqual(product.slug, "test-product")
        self.assertIsInstance(product.product_id, uuid.UUID)

    def test_product_creation_minimal_fields(self):
        """Test creating product with only required fields"""
        product = Product.objects.create(
            name="Minimal Product",
            description="Minimal description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.name, "Minimal Product")
        self.assertEqual(product.unit_price, Decimal("50.00"))
        self.assertIsNone(product.original_price)
        self.assertEqual(product.in_stock, 0)
        self.assertEqual(product.min_order_quantity, 1)
        self.assertIsNone(product.max_order_quantity)
        self.assertFalse(product.featured)
        self.assertFalse(product.product_image)

    def test_product_slug_generation_unique(self):
        """Test automatic unique slug generation"""
        # Create first product
        _ = Product.objects.create(
            name="Duplicate Name",
            description="First product",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        # Create second product with same name by same user (should fail due to unique_together)
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name="Duplicate Name",
                description="Second product",
                unit_price=Decimal("60.00"),
                category=self.category,
                created_by=self.user,
            )

    def test_product_slug_generation_different_users(self):
        """Test slug generation for same product name by different users"""
        # Create product by first user
        product1 = Product.objects.create(
            name="Same Name Product",
            description="First product",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        # Create product with same name by different user
        product2 = Product.objects.create(
            name="Same Name Product",
            description="Second product",
            unit_price=Decimal("60.00"),
            category=self.category,
            created_by=self.admin_user,
        )

        self.assertEqual(product1.slug, "same-name-product")
        self.assertEqual(product2.slug, "same-name-product-1")

    def test_product_slug_generation_complex_names(self):
        """Test slug generation with complex product names"""
        product = Product.objects.create(
            name="Complex Product Name!@# With $pecial Ch@rs",
            description="Test description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.slug, "complex-product-name-with-pecial-chrs")

    def test_product_unique_together_constraint(self):
        """Test unique_together constraint for created_by and name"""
        Product.objects.create(
            name="Unique Product",
            description="First product",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        # Same user cannot create product with same name
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name="Unique Product",
                description="Duplicate product",
                unit_price=Decimal("60.00"),
                category=self.category,
                created_by=self.user,
            )

    def test_product_str_method(self):
        """Test product string representation"""
        product = Product.objects.create(
            name="Test Product",
            description="Test description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(str(product), "Test Product")

    def test_product_with_image(self):
        """Test product creation with image"""
        image = SimpleUploadedFile(
            name="test_product.jpg",
            content=b"fake image content",
            content_type="image/jpeg",
        )

        product = Product.objects.create(
            name="Image Product",
            description="Test description",
            unit_price=Decimal("50.00"),
            product_image=image,
            category=self.category,
            created_by=self.user,
        )

        self.assertIsNotNone(product.product_image)

    def test_product_negative_quantities(self):
        """Test that negative quantities are not allowed"""
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name="Negative Stock",
                description="Test description",
                unit_price=Decimal("50.00"),
                in_stock=-1,  # Should fail
                category=self.category,
                created_by=self.user,
            )

    def test_product_protect_on_category_delete(self):
        """Test that product is protected when category is deleted"""
        product = Product.objects.create(
            name="Protected Product",
            description="Test description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        with self.assertRaises(Exception):  # Should raise ProtectedError
            self.category.delete()

        # Product should still exist
        self.assertTrue(Product.objects.filter(product_id=product.product_id).exists())


class CategorySerializerTests(TestCase):
    """Test cases for CategorySerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

    def test_category_serializer_valid_data(self):
        """Test category serializer with valid data"""
        data = {
            "name": "Test Category",
            "description": "Test description",
            "is_active": True,
        }

        serializer = CategorySerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_category_serializer_required_fields(self):
        """Test category serializer with missing required fields"""
        data = {"description": "Test description"}

        serializer = CategorySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_category_serializer_read_only_fields(self):
        """Test that read-only fields are not included in create/update"""
        data = {
            "name": "Test Category",
            "category_id": uuid.uuid4(),
            "slug": "custom-slug",
            "created_by": self.user.user_id,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }

        serializer = CategorySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Read-only fields should not be in validated_data
        self.assertNotIn("category_id", serializer.validated_data)
        self.assertNotIn("slug", serializer.validated_data)
        self.assertNotIn("created_by", serializer.validated_data)
        self.assertNotIn("created_at", serializer.validated_data)
        self.assertNotIn("updated_at", serializer.validated_data)

    def test_category_serializer_name_max_length(self):
        """Test category name max length validation"""
        data = {
            "name": "x" * 101,  # Exceeds max_length of 100
            "description": "Test description",
        }

        serializer = CategorySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)


class ProductSerializerTests(TestCase):
    """Test cases for ProductSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.category = Category.objects.create(
            name="Test Category", created_by=self.user
        )

    def test_product_serializer_valid_data(self):
        """Test product serializer with valid data"""
        data = {
            "name": "Test Product",
            "description": "Test description",
            "unit_price": "99.99",
            "original_price": "149.99",
            "in_stock": 100,
            "min_order_quantity": 1,
            "max_order_quantity": 50,
            "featured": True,
            "category": self.category.category_id,
        }

        # Mock request context
        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            data=data, context={"request": MockRequest(self.user)}
        )
        self.assertTrue(serializer.is_valid())

    def test_product_serializer_required_fields(self):
        """Test product serializer with missing required fields"""
        data = {"description": "Test description"}

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            data=data, context={"request": MockRequest(self.user)}
        )
        self.assertFalse(serializer.is_valid())

        # Check that required fields are in errors
        required_fields = ["name", "unit_price", "category"]
        for field in required_fields:
            self.assertIn(field, serializer.errors)

    def test_product_serializer_duplicate_name_same_user(self):
        """Test validation for duplicate product name by same user"""
        # Create existing product
        Product.objects.create(
            name="Existing Product",
            description="Existing description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        data = {
            "name": "Existing Product",
            "description": "New description",
            "unit_price": "60.00",
            "category": self.category.category_id,
        }

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            data=data, context={"request": MockRequest(self.user)}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
        self.assertEqual(
            serializer.errors["name"][0], "You already have a product with this name."
        )

    def test_product_serializer_duplicate_name_different_user(self):
        """Test that different users can have products with same name"""
        user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            first_name="Test2",
            last_name="User2",
            password="testpass123",
        )

        # Create product by first user
        Product.objects.create(
            name="Same Name Product",
            description="First description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        data = {
            "name": "Same Name Product",
            "description": "Second description",
            "unit_price": "60.00",
            "category": self.category.category_id,
        }

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            data=data, context={"request": MockRequest(user2)}
        )
        self.assertTrue(serializer.is_valid())

    def test_product_serializer_update_validation(self):
        """Test validation during product update"""
        # Create two products by same user
        _ = Product.objects.create(
            name="Product 1",
            description="Description 1",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        product2 = Product.objects.create(
            name="Product 2",
            description="Description 2",
            unit_price=Decimal("60.00"),
            category=self.category,
            created_by=self.user,
        )

        # Try to update product2 with product1's name
        data = {
            "name": "Product 1",
            "description": "Updated description",
            "unit_price": "70.00",
            "category": self.category.category_id,
        }

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            instance=product2, data=data, context={"request": MockRequest(self.user)}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_product_serializer_update_same_name(self):
        """Test updating product with same name (should be allowed)"""
        product = Product.objects.create(
            name="Test Product",
            description="Original description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        data = {
            "name": "Test Product",  # Same name
            "description": "Updated description",
            "unit_price": "60.00",
            "category": self.category.category_id,
        }

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            instance=product, data=data, context={"request": MockRequest(self.user)}
        )
        self.assertTrue(serializer.is_valid())

    def test_product_serializer_read_only_fields(self):
        """Test that read-only fields are not included in validation"""
        data = {
            "name": "Test Product",
            "description": "Test description",
            "unit_price": "99.99",
            "category": self.category.category_id,
            "product_id": uuid.uuid4(),
            "slug": "custom-slug",
            "created_by": self.user.user_id,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = ProductSerializer(
            data=data, context={"request": MockRequest(self.user)}
        )
        self.assertTrue(serializer.is_valid())

        # Read-only fields should not be in validated_data
        read_only_fields = [
            "product_id",
            "slug",
            "created_by",
            "created_at",
            "updated_at",
        ]
        for field in read_only_fields:
            self.assertNotIn(field, serializer.validated_data)


class CategoryViewSetTests(APITestCase):
    """Test cases for CategoryViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="adminpass123",
            role="admin",
            is_staff=True,
            is_active=True,
        )

        self.regular_user = User.objects.create_user(
            username="user",
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            password="userpass123",
            role="customer",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Test Category",
            description="Test description",
            created_by=self.admin_user,
        )

        # Generate tokens
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)
        self.user_token = str(RefreshToken.for_user(self.regular_user).access_token)

    def test_category_list_anonymous_user(self):
        """Test that anonymous users can view categories"""
        url = "/api/categories/"  # Adjust URL based on your routing
        response = self.client.get(url)

        # Should allow read access for anonymous users
        self.assertIn(
            response.status_code, [200, 401]
        )  # Depends on permission settings

    def test_category_list_authenticated_user(self):
        """Test category list for authenticated users"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = "/api/categories/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_category_create_admin_user(self):
        """Test category creation by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/categories/"

        data = {
            "name": "New Category",
            "description": "New description",
            "is_active": True,
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Verify category was created
        category = Category.objects.get(name="New Category")
        self.assertEqual(category.created_by, self.admin_user)
        self.assertEqual(category.description, "New description")

    def test_category_create_regular_user(self):
        """Test category creation by regular user (should be forbidden)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = "/api/categories/"

        data = {"name": "New Category", "description": "New description"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 403)

    def test_category_create_anonymous_user(self):
        """Test category creation by anonymous user (should be unauthorized)"""
        url = "/api/categories/"

        data = {"name": "New Category", "description": "New description"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 401)

    def test_category_create_duplicate_name(self):
        """Test creating category with duplicate name"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/categories/"

        data = {
            "name": "Test Category",  # Already exists
            "description": "Another description",
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_category_retrieve(self):
        """Test retrieving a specific category"""
        url = f"/api/categories/{self.category.category_id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Test Category")

    def test_category_update_admin_user(self):
        """Test category update by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/categories/{self.category.category_id}/"

        data = {
            "name": "Updated Category",
            "description": "Updated description",
            "is_active": False,
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify update
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Updated Category")
        self.assertEqual(self.category.description, "Updated description")
        self.assertFalse(self.category.is_active)

    def test_category_partial_update(self):
        """Test category partial update"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/categories/{self.category.category_id}/"

        data = {"description": "Partially updated description"}

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify partial update
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Test Category")  # Unchanged
        self.assertEqual(self.category.description, "Partially updated description")

    def test_category_delete_admin_user(self):
        """Test category deletion by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/categories/{self.category.category_id}/"

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

        # Verify deletion
        self.assertFalse(
            Category.objects.filter(category_id=self.category.category_id).exists()
        )

    def test_category_delete_regular_user(self):
        """Test category deletion by regular user (should be forbidden)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = f"/api/categories/{self.category.category_id}/"

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)

    def test_category_nonexistent(self):
        """Test operations on nonexistent category"""
        fake_uuid = uuid.uuid4()
        url = f"/api/categories/{fake_uuid}/"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class ProductViewSetTests(APITestCase):
    """Test cases for ProductViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="adminpass123",
            role="admin",
            is_staff=True,
            is_active=True,
        )

        self.regular_user = User.objects.create_user(
            username="user",
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            password="userpass123",
            role="customer",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Test Category", created_by=self.admin_user
        )

        self.product = Product.objects.create(
            name="Test Product",
            description="Test description",
            unit_price=Decimal("99.99"),
            category=self.category,
            created_by=self.admin_user,
        )

        # Generate tokens
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)
        self.user_token = str(RefreshToken.for_user(self.regular_user).access_token)

    def test_product_list_anonymous_user(self):
        """Test that anonymous users can view products"""
        url = "/api/products/"
        response = self.client.get(url)

        # Should allow read access for anonymous users based on permission class
        self.assertIn(response.status_code, [200, 401])

    def test_product_list_authenticated_user(self):
        """Test product list for authenticated users"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = "/api/products/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_product_create_admin_user(self):
        """Test product creation by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "New Product",
            "description": "New product description",
            "unit_price": "149.99",
            "original_price": "199.99",
            "in_stock": 50,
            "min_order_quantity": 1,
            "max_order_quantity": 25,
            "featured": True,
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)

        # Verify product was created
        product = Product.objects.get(name="New Product")
        self.assertEqual(product.created_by, self.admin_user)
        self.assertEqual(product.unit_price, Decimal("149.99"))
        self.assertEqual(product.original_price, Decimal("199.99"))
        self.assertEqual(product.in_stock, 50)
        self.assertTrue(product.featured)

    def test_product_create_regular_user(self):
        """Test product creation by regular user (should be forbidden)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = "/api/products/"

        data = {
            "name": "New Product",
            "description": "New product description",
            "unit_price": "149.99",
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 403)

    def test_product_create_anonymous_user(self):
        """Test product creation by anonymous user (should be unauthorized)"""
        url = "/api/products/"

        data = {
            "name": "New Product",
            "description": "New product description",
            "unit_price": "149.99",
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 401)

    def test_product_create_duplicate_name_same_user(self):
        """Test creating product with duplicate name by same user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "Test Product",  # Already exists for this user
            "description": "Another description",
            "unit_price": "199.99",
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_product_create_missing_required_fields(self):
        """Test product creation with missing required fields"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "Incomplete Product"
            # Missing description, unit_price, category
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)

        # Check that required fields are in errors
        required_fields = ["description", "unit_price", "category"]
        for field in required_fields:
            self.assertIn(field, response.data)

    def test_product_create_invalid_price(self):
        """Test product creation with invalid price"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "Invalid Price Product",
            "description": "Test description",
            "unit_price": "invalid_price",
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("unit_price", response.data)

    def test_product_create_negative_stock(self):
        """Test product creation with negative stock"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "Negative Stock Product",
            "description": "Test description",
            "unit_price": "99.99",
            "in_stock": -1,
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("in_stock", response.data)

    def test_product_create_invalid_quantities(self):
        """Test product creation with invalid min/max quantities"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        data = {
            "name": "Invalid Quantity Product",
            "description": "Test description",
            "unit_price": "99.99",
            "min_order_quantity": 0,  # Should be at least 1
            "max_order_quantity": -5,  # Should be positive
            "category": str(self.category.category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_product_create_nonexistent_category(self):
        """Test product creation with nonexistent category"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = "/api/products/"

        fake_category_id = uuid.uuid4()
        data = {
            "name": "Orphan Product",
            "description": "Test description",
            "unit_price": "99.99",
            "category": str(fake_category_id),
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)

    def test_product_retrieve(self):
        """Test retrieving a specific product"""
        url = f"/api/products/{self.product.product_id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Test Product")
        self.assertEqual(response.data["unit_price"], "99.99")

    def test_product_update_admin_user(self):
        """Test product update by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/products/{self.product.product_id}/"

        data = {
            "name": "Updated Product",
            "description": "Updated description",
            "unit_price": "129.99",
            "original_price": "179.99",
            "in_stock": 75,
            "featured": True,
            "category": str(self.category.category_id),
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify update
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Updated Product")
        self.assertEqual(self.product.unit_price, Decimal("129.99"))
        self.assertEqual(self.product.in_stock, 75)
        self.assertTrue(self.product.featured)

    def test_product_partial_update(self):
        """Test product partial update"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/products/{self.product.product_id}/"

        data = {"unit_price": "89.99", "in_stock": 150}

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify partial update
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Test Product")  # Unchanged
        self.assertEqual(self.product.unit_price, Decimal("89.99"))
        self.assertEqual(self.product.in_stock, 150)

    def test_product_update_duplicate_name(self):
        """Test updating product with duplicate name"""
        # Create another product by the same user
        other_product = Product.objects.create(
            name="Other Product",
            description="Other description",
            unit_price=Decimal("79.99"),
            category=self.category,
            created_by=self.admin_user,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/products/{other_product.product_id}/"

        data = {
            "name": "Test Product",  # Trying to use existing name
            "description": "Updated description",
            "unit_price": "89.99",
            "category": str(self.category.category_id),
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_product_update_same_name(self):
        """Test updating product with its own name (should be allowed)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/products/{self.product.product_id}/"

        data = {
            "name": "Test Product",  # Same name
            "description": "Updated description",
            "unit_price": "109.99",
            "category": str(self.category.category_id),
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify update
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, "Updated description")
        self.assertEqual(self.product.unit_price, Decimal("109.99"))

    def test_product_update_regular_user(self):
        """Test product update by regular user (should be forbidden)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = f"/api/products/{self.product.product_id}/"

        data = {
            "name": "Unauthorized Update",
            "description": "Should not work",
            "unit_price": "999.99",
            "category": str(self.category.category_id),
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, 403)

    def test_product_delete_admin_user(self):
        """Test product deletion by admin user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        url = f"/api/products/{self.product.product_id}/"

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

        # Verify deletion
        self.assertFalse(
            Product.objects.filter(product_id=self.product.product_id).exists()
        )

    def test_product_delete_regular_user(self):
        """Test product deletion by regular user (should be forbidden)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        url = f"/api/products/{self.product.product_id}/"

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)

    def test_product_nonexistent(self):
        """Test operations on nonexistent product"""
        fake_uuid = uuid.uuid4()
        url = f"/api/products/{fake_uuid}/"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_product_queryset_filtering(self):
        """Test that products are properly filtered in queryset"""
        # Create products by different users
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            first_name="User2",
            last_name="Test",
            password="testpass123",
            is_active=True,
        )

        Product.objects.create(
            name="User2 Product",
            description="Product by user2",
            unit_price=Decimal("49.99"),
            category=self.category,
            created_by=user2,
        )

        url = "/api/products/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should return all products (no filtering by user in viewset)
        self.assertEqual(len(response.data), 2)

    def test_product_ordering(self):
        """Test product ordering in list view"""
        # Create additional products
        Product.objects.create(
            name="Alpha Product",
            description="First alphabetically",
            unit_price=Decimal("29.99"),
            category=self.category,
            created_by=self.admin_user,
        )

        Product.objects.create(
            name="Zulu Product",
            description="Last alphabetically",
            unit_price=Decimal("39.99"),
            category=self.category,
            created_by=self.admin_user,
        )

        url = "/api/products/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        # Products should be ordered by creation time (newest first by default)
        # or you can test custom ordering if implemented

    def test_product_featured_filtering(self):
        """Test filtering products by featured status"""
        # Create featured and non-featured products
        Product.objects.create(
            name="Featured Product",
            description="This is featured",
            unit_price=Decimal("199.99"),
            featured=True,
            category=self.category,
            created_by=self.admin_user,
        )

        Product.objects.create(
            name="Regular Product",
            description="This is not featured",
            unit_price=Decimal("99.99"),
            featured=False,
            category=self.category,
            created_by=self.admin_user,
        )

        # Test filtering by featured status (if implemented)
        url = "/api/products/?featured=true"
        response = self.client.get(url)

        # This test assumes you have filtering implemented
        # Adjust based on your actual filtering implementation
        self.assertEqual(response.status_code, 200)

    def test_product_category_relationship(self):
        """Test product-category relationship in API responses"""
        url = f"/api/products/{self.product.product_id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["category"]), str(self.category.category_id))

    def test_product_search_functionality(self):
        """Test product search functionality if implemented"""
        # Create products with searchable content
        Product.objects.create(
            name="Searchable Laptop",
            description="High performance laptop for gaming",
            unit_price=Decimal("1299.99"),
            category=self.category,
            created_by=self.admin_user,
        )

        # Test search (if implemented)
        url = "/api/products/?search=laptop"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Verify search results based on your implementation


class EdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.category = Category.objects.create(
            name="Edge Case Category", created_by=self.user
        )

    def test_product_max_decimal_values(self):
        """Test products with maximum decimal values"""
        product = Product.objects.create(
            name="Max Price Product",
            description="Testing maximum price values",
            unit_price=Decimal(
                "99999999.99"
            ),  # Maximum for DecimalField(max_digits=10, decimal_places=2)
            original_price=Decimal("99999999.99"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.unit_price, Decimal("99999999.99"))
        self.assertEqual(product.original_price, Decimal("99999999.99"))

    def test_product_zero_prices(self):
        """Test products with zero prices"""
        product = Product.objects.create(
            name="Free Product",
            description="Testing zero price",
            unit_price=Decimal("0.00"),
            original_price=Decimal("0.00"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.unit_price, Decimal("0.00"))
        self.assertEqual(product.original_price, Decimal("0.00"))

    def test_product_large_quantities(self):
        """Test products with very large quantities"""
        product = Product.objects.create(
            name="Bulk Product",
            description="Testing large quantities",
            unit_price=Decimal("1.00"),
            in_stock=2147483647,  # Maximum for PositiveIntegerField
            min_order_quantity=1,
            max_order_quantity=2147483647,
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(product.in_stock, 2147483647)
        self.assertEqual(product.max_order_quantity, 2147483647)

    def test_category_and_product_unicode_names(self):
        """Test categories and products with unicode characters"""
        unicode_category = Category.objects.create(
            name="Категория тест 中文 🎉", created_by=self.user
        )

        unicode_product = Product.objects.create(
            name="Продукт тест 中文产品 🚀",
            description="Unicode description with émojis 🌟",
            unit_price=Decimal("99.99"),
            category=unicode_category,
            created_by=self.user,
        )

        self.assertEqual(unicode_category.name, "Категория тест 中文 🎉")
        self.assertEqual(unicode_product.name, "Продукт тест 中文产品 🚀")
        # Verify slug generation handles unicode
        self.assertIsNotNone(unicode_category.slug)
        self.assertIsNotNone(unicode_product.slug)

    def test_very_long_descriptions(self):
        """Test products with very long descriptions"""
        long_description = "A" * 10000  # Very long description

        product = Product.objects.create(
            name="Long Description Product",
            description=long_description,
            unit_price=Decimal("99.99"),
            category=self.category,
            created_by=self.user,
        )

        self.assertEqual(len(product.description), 10000)

    def test_slug_collision_handling(self):
        """Test slug collision handling with many similar names"""
        base_name = "Similar Product Name"
        products = []

        # Create multiple products with similar names
        for i in range(10):
            product = Product.objects.create(
                name=f"{base_name} {i}" if i > 0 else base_name,
                description=f"Description {i}",
                unit_price=Decimal("99.99"),
                category=self.category,
                created_by=self.user,
            )
            products.append(product)

        # Verify all slugs are unique
        slugs = [p.slug for p in products]
        self.assertEqual(len(slugs), len(set(slugs)), "All slugs should be unique")

    def test_product_with_null_optional_fields(self):
        """Test products with all optional fields as null/default"""
        product = Product.objects.create(
            name="Minimal Product",
            description="Required description",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
            # All other fields should use defaults
        )

        self.assertIsNone(product.original_price)
        self.assertEqual(product.in_stock, 0)
        self.assertEqual(product.min_order_quantity, 1)
        self.assertIsNone(product.max_order_quantity)
        self.assertFalse(product.featured)
        self.assertFalse(product.product_image)

    def test_concurrent_slug_generation(self):
        """Test slug generation under concurrent conditions"""
        # This would require threading/multiprocessing to test properly
        # For now, just test the logic

        # Create a product with a specific name
        product1 = Product.objects.create(
            name="Concurrent Test",
            description="First product",
            unit_price=Decimal("50.00"),
            category=self.category,
            created_by=self.user,
        )

        # Simulate what would happen if another product was created concurrently
        # by a different user with the same name
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            first_name="User2",
            last_name="Test",
            password="testpass123",
        )

        product2 = Product.objects.create(
            name="Concurrent Test",
            description="Second product",
            unit_price=Decimal("60.00"),
            category=self.category,
            created_by=user2,
        )

        # Slugs should be different
        self.assertNotEqual(product1.slug, product2.slug)

    def test_category_cascade_behavior(self):
        """Test category deletion behavior with related products"""
        # Create a product in the category
        product = Product.objects.create(
            name="Dependent Product",
            description="This product depends on category",
            unit_price=Decimal("99.99"),
            category=self.category,
            created_by=self.user,
        )

        # Try to delete category (should be protected)
        with self.assertRaises(Exception):
            self.category.delete()

        # Product should still exist
        self.assertTrue(Product.objects.filter(product_id=product.product_id).exists())
        # Category should still exist
        self.assertTrue(
            Category.objects.filter(category_id=self.category.category_id).exists()
        )

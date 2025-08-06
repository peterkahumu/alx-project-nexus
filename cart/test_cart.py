import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from cart.models import Cart, CartItem
from cart.serializers import CartItemSerializer, CartSerializer, ProductInCartSerializer
from products.models import Category, Product

User = get_user_model()


class CartModelTestCase(TestCase):
    """Test cases for Cart model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.cart, _ = Cart.objects.get_or_create(user=self.user)

    def test_cart_creation(self):
        """Test creating a cart"""
        self.assertIsInstance(self.cart.cart_id, uuid.UUID)
        self.assertEqual(self.cart.user, self.user)
        self.assertTrue(self.cart.created_at)

    def test_cart_str_representation(self):
        """Test cart string representation"""
        expected_str = f"{self.cart.cart_id} - {self.user.username}"
        self.assertEqual(str(self.cart), expected_str)

    def test_user_cart_relationship(self):
        """Test one-to-one relationship between user and cart"""
        # Access cart through user
        self.assertEqual(str(self.user.cart), str(self.cart))

        # Ensure cart_id is unique
        self.assertTrue(Cart.objects.filter(cart_id=self.cart.cart_id).exists())


class CartItemModelTestCase(TestCase):
    """Test cases for CartItem model"""

    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        # Create category
        self.category = Category.objects.create(
            name="Electronics", description="Electronic products", created_by=self.user
        )

        # Create product
        self.product = Product.objects.create(
            name="Test Laptop",
            description="A test laptop",
            unit_price=Decimal("999.99"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        # Create cart
        self.cart, _ = Cart.objects.get_or_create(user=self.user)

    def test_cart_item_creation(self):
        """Test creating a cart item"""
        cart_item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=2
        )

        self.assertIsInstance(cart_item.item_id, uuid.UUID)
        self.assertEqual(cart_item.cart, self.cart)
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 2)

    def test_cart_item_str_representation(self):
        """Test cart item string representation"""
        cart_item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=3
        )

        expected_str = f"3 X {self.product.name}"
        self.assertEqual(str(cart_item), expected_str)

    def test_get_total_price(self):
        """Test cart item total price calculation"""
        cart_item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=2
        )

        expected_total = Decimal("999.99") * 2
        self.assertEqual(cart_item.get_total_price(), expected_total)

    def test_unique_cart_product_constraint(self):
        """Test that cart-product combination must be unique"""
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

        # Creating another item with same cart and product should raise error
        with self.assertRaises(Exception):  # IntegrityError in real DB
            CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)


class CartSerializerTestCase(TestCase):
    """Test cases for cart serializers"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        self.category = Category.objects.create(
            name="Electronics", description="Electronic products", created_by=self.user
        )

        self.product = Product.objects.create(
            name="Test Laptop",
            description="A test laptop",
            unit_price=Decimal("999.99"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.cart, _ = Cart.objects.get_or_create(user=self.user)

    def test_product_in_cart_serializer(self):
        """Test ProductInCartSerializer"""
        serializer = ProductInCartSerializer(self.product)
        data = serializer.data

        self.assertEqual(data["product_id"], str(self.product.product_id))
        self.assertEqual(data["name"], self.product.name)
        self.assertEqual(data["unit_price"], str(self.product.unit_price))

    def test_cart_item_serializer_read(self):
        """Test CartItemSerializer for reading"""
        cart_item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=2
        )

        serializer = CartItemSerializer(cart_item)
        data = serializer.data

        self.assertEqual(str(data["item_id"]), str(cart_item.item_id))
        self.assertEqual(data["quantity"], 2)
        self.assertEqual(data["product"]["name"], self.product.name)
        self.assertEqual(data["get_total_price"], cart_item.get_total_price())

    def test_cart_item_serializer_write(self):
        """Test CartItemSerializer for writing"""
        data = {"product_id": self.product.product_id, "quantity": 3}

        serializer = CartItemSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        cart_item = serializer.save(cart=self.cart)
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 3)

    def test_cart_serializer(self):
        """Test CartSerializer"""
        # Create cart items
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)

        serializer = CartSerializer(self.cart)
        data = serializer.data

        self.assertEqual(str(data["cart_id"]), str(self.cart.cart_id))
        self.assertEqual(str(data["user"]), str(self.user.user_id))
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["quantity"], 2)


class CartAPITestCase(APITestCase):
    """Test cases for Cart API endpoints"""

    def setUp(self):
        # Create users with unique usernames and emails
        self.user1 = User.objects.create_user(
            username=f"user1_{uuid.uuid4().hex[:8]}",
            email=f"user1_{uuid.uuid4().hex[:8]}@example.com",
            first_name="User",
            last_name="One",
            password="testpass123",
        )

        self.user2 = User.objects.create_user(
            username=f"user2_{uuid.uuid4().hex[:8]}",
            email=f"user2_{uuid.uuid4().hex[:8]}@example.com",
            first_name="User",
            last_name="Two",
            password="testpass123",
        )

        # Create category
        self.category = Category.objects.create(
            name=f"Electronics_{uuid.uuid4().hex[:8]}",
            description="Electronic products",
            created_by=self.user1,
        )

        # Create products
        self.product1 = Product.objects.create(
            name=f"Laptop_{uuid.uuid4().hex[:8]}",
            description="A laptop",
            unit_price=Decimal("999.99"),
            in_stock=10,
            category=self.category,
            created_by=self.user1,
        )

        self.product2 = Product.objects.create(
            name=f"Mouse_{uuid.uuid4().hex[:8]}",
            description="A computer mouse",
            unit_price=Decimal("29.99"),
            in_stock=50,
            category=self.category,
            created_by=self.user1,
        )

        # Setup API client
        self.client = APIClient()

    def authenticate_user(self, user):
        """Helper method to authenticate user"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_cart_list_authenticated(self):
        """Test listing carts for authenticated user"""
        self.authenticate_user(self.user1)
        cart, _ = Cart.objects.get_or_create(user=self.user1)

        url = reverse("cart-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cart_id"], str(cart.cart_id))

    def test_cart_list_unauthenticated(self):
        """Test that unauthenticated users cannot access carts"""
        url = reverse("cart-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cart_create(self):
        """Test creating a cart"""
        self.authenticate_user(self.user1)

        url = reverse("cart-list")
        data = {}
        response = self.client.post(url, data)

        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED]
        )
        self.assertTrue(Cart.objects.filter(user=self.user1).exists())

    def test_cart_isolation_between_users(self):
        """Test that users can only see their own carts"""
        # Create carts for both users
        cart1, _ = Cart.objects.get_or_create(user=self.user1)
        cart2, _ = Cart.objects.get_or_create(user=self.user2)

        # User1 should only see their cart
        self.authenticate_user(self.user1)
        url = reverse("cart-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cart_id"], str(cart1.cart_id))

        # User2 should only see their cart
        self.authenticate_user(self.user2)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cart_id"], str(cart2.cart_id))


class CartItemAPITestCase(APITestCase):
    """Test cases for CartItem API endpoints"""

    def setUp(self):
        # Create user with unique identifiers
        self.user = User.objects.create_user(
            username=f"testuser_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        # Create category
        self.category = Category.objects.create(
            name=f"Electronics_{uuid.uuid4().hex[:8]}",
            description="Electronic products",
            created_by=self.user,
        )

        # Create products
        self.product1 = Product.objects.create(
            name=f"Laptop_{uuid.uuid4().hex[:8]}",
            description="A laptop",
            unit_price=Decimal("999.99"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.product2 = Product.objects.create(
            name=f"Mouse_{uuid.uuid4().hex[:8]}",
            description="A computer mouse",
            unit_price=Decimal("29.99"),
            in_stock=50,
            category=self.category,
            created_by=self.user,
        )

        # Setup API client
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_add_item_to_cart(self):
        """Test adding an item to cart"""
        url = reverse("cart-items-list")
        data = {"product_id": str(self.product1.product_id), "quantity": 2}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CartItem.objects.filter(
                cart__user=self.user, product=self.product1
            ).exists()
        )

        cart_item = CartItem.objects.get(cart__user=self.user, product=self.product1)
        self.assertEqual(cart_item.quantity, 2)

    def test_add_existing_item_to_cart(self):
        """Test adding an item that already exists in cart (should update quantity)"""
        # First, add item via API to ensure cart is created
        url = reverse("cart-items-list")
        data = {"product_id": str(self.product1.product_id), "quantity": 1}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Now add the same item again
        data = {"product_id": str(self.product1.product_id), "quantity": 2}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that quantity was updated, not a new item created
        cart_items = CartItem.objects.filter(
            cart__user=self.user, product=self.product1
        )
        self.assertEqual(cart_items.count(), 1)

        cart_item = cart_items.first()
        self.assertEqual(cart_item.quantity, 3)  # 1 + 2 = 3

    def test_add_item_creates_cart_if_not_exists(self):
        """Test that adding item creates cart if user doesn't have one"""
        # Ensure no cart exists for this user
        Cart.objects.filter(user=self.user).delete()

        url = reverse("cart-items-list")
        data = {"product_id": str(self.product1.product_id), "quantity": 1}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_add_item_with_invalid_product(self):
        """Test adding item with invalid product ID"""
        url = reverse("cart-items-list")
        data = {"product_id": str(uuid.uuid4()), "quantity": 1}  # Random UUID

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_item_with_invalid_data(self):
        """Test adding item with invalid data"""
        url = reverse("cart-items-list")
        data = {"product_id": "invalid-uuid", "quantity": -1}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_cart_items(self):
        """Test listing cart items for authenticated user"""
        # Create cart first, then add items
        cart, _ = Cart.objects.get_or_create(user=self.user)
        item1 = CartItem.objects.create(cart=cart, product=self.product1, quantity=2)
        item2 = CartItem.objects.create(cart=cart, product=self.product2, quantity=1)

        url = reverse("cart-items-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Check that items belong to the authenticated user
        item_ids = [item["item_id"] for item in response.data]
        self.assertIn(str(item1.item_id), item_ids)
        self.assertIn(str(item2.item_id), item_ids)

    def test_update_cart_item(self):
        """Test updating cart item quantity"""
        cart, _ = Cart.objects.get_or_create(user=self.user)
        cart_item = CartItem.objects.create(
            cart=cart, product=self.product1, quantity=1
        )

        url = reverse("cart-items-detail", kwargs={"pk": cart_item.item_id})
        data = {"product_id": str(self.product1.product_id), "quantity": 5}

        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 5)

    def test_delete_cart_item(self):
        """Test deleting cart item"""
        cart, _ = Cart.objects.get_or_create(user=self.user)
        cart_item = CartItem.objects.create(
            cart=cart, product=self.product1, quantity=1
        )

        url = reverse("cart-items-detail", kwargs={"pk": cart_item.item_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CartItem.objects.filter(item_id=cart_item.item_id).exists())

    def test_cart_item_isolation_between_users(self):
        """Test that users can only access their own cart items"""
        # Create another user and cart
        other_user = User.objects.create_user(
            username=f"otheruser_{uuid.uuid4().hex[:8]}",
            email=f"other_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Other",
            last_name="User",
            password="testpass123",
        )
        other_cart, _ = Cart.objects.get_or_create(user=other_user)
        other_item = CartItem.objects.create(
            cart=other_cart, product=self.product1, quantity=1
        )

        # Try to access other user's cart item
        url = reverse("cart-items-detail", kwargs={"pk": other_item.item_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cart_item_total_price_in_response(self):
        """Test that cart item response includes total price"""
        cart, _ = Cart.objects.get_or_create(user=self.user)
        cart_item = CartItem.objects.create(
            cart=cart, product=self.product1, quantity=2
        )

        url = reverse("cart-items-detail", kwargs={"pk": cart_item.item_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_total = float(self.product1.unit_price * 2)
        self.assertEqual(float(response.data["get_total_price"]), expected_total)


class CartIntegrationTestCase(APITestCase):
    """Integration tests for cart functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username=f"testuser_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        self.category = Category.objects.create(
            name=f"Electronics_{uuid.uuid4().hex[:8]}",
            description="Electronic products",
            created_by=self.user,
        )

        self.product = Product.objects.create(
            name=f"Laptop_{uuid.uuid4().hex[:8]}",
            description="A laptop",
            unit_price=Decimal("999.99"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_complete_cart_workflow(self):
        """Test complete cart workflow: create cart, add items, view cart with items"""
        # Step 1: Add item to cart (this should create cart automatically)
        add_item_url = reverse("cart-items-list")
        add_data = {"product_id": str(self.product.product_id), "quantity": 2}

        add_response = self.client.post(add_item_url, add_data)
        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)

        # Step 2: Verify cart was created
        self.assertTrue(Cart.objects.filter(user=self.user).exists())
        cart = Cart.objects.get(user=self.user)

        # Step 3: Get cart with items
        cart_url = reverse("cart-list")
        cart_response = self.client.get(cart_url)

        self.assertEqual(cart_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cart_response.data["cart_id"], str(cart.cart_id))
        self.assertEqual(len(cart_response.data["items"]), 1)

        item_data = cart_response.data["items"][0]
        self.assertEqual(item_data["quantity"], 2)
        self.assertEqual(item_data["product"]["name"], self.product.name)

        # Step 4: Add same item again (should update quantity)
        add_response2 = self.client.post(add_item_url, add_data)
        self.assertEqual(add_response2.status_code, status.HTTP_200_OK)

        # Step 5: Verify quantity was updated
        cart_response2 = self.client.get(cart_url)
        item_data2 = cart_response2.data["items"][0]
        self.assertEqual(item_data2["quantity"], 4)  # 2 + 2 = 4

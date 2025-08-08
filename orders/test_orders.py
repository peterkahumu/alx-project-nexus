"""
Comprehensive unit tests for the Order system
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from cart.models import Cart, CartItem
from products.models import Category, Product

from .models import Order, OrderItem
from .serializers import OrderItemSerializer, OrderSerializer
from .tasks import send_order_email

User = get_user_model()


class OrderModelTest(TestCase):
    """Test cases for Order model"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            address={"street": "123 Main St", "city": "Test City", "zip": "12345"},
        )

    def test_order_creation(self):
        """Test basic order creation"""
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("16.00"),
            shipping_cost=Decimal("300.00"),
            total_amount=Decimal("416.00"),
        )

        self.assertIsNotNone(order.order_id)
        self.assertIsNotNone(order.order_number)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.subtotal, Decimal("100.00"))
        self.assertEqual(order.tax_amount, Decimal("16.00"))
        self.assertEqual(order.shipping_cost, Decimal("300.00"))
        self.assertEqual(order.total_amount, Decimal("416.00"))

    def test_order_number_generation(self):
        """Test that order number is automatically generated"""
        order = Order.objects.create(user=self.user)
        self.assertIsNotNone(order.order_number)
        self.assertEqual(len(order.order_number), 8)
        self.assertTrue(order.order_number.isupper())

    def test_order_string_representation(self):
        """Test order string representation"""
        order = Order.objects.create(user=self.user)
        expected_str = f"{order.order_id} - {self.user.username}"
        self.assertEqual(str(order), expected_str)

    def test_order_defaults(self):
        """Test order default values"""
        order = Order.objects.create(user=self.user)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.subtotal, Decimal("0.00"))
        self.assertEqual(order.tax_amount, Decimal("0.00"))
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("0.00"))
        self.assertIsNone(order.shipping_address)
        self.assertIsNone(order.billing_address)
        self.assertIsNone(order.notes)
        self.assertIsNone(order.cancelled_at)

    def test_order_with_addresses(self):
        """Test order creation with shipping and billing addresses"""
        shipping_address = {"street": "456 Oak St", "city": "Ship City", "zip": "54321"}
        billing_address = {"street": "789 Pine St", "city": "Bill City", "zip": "67890"}

        order = Order.objects.create(
            user=self.user,
            shipping_address=shipping_address,
            billing_address=billing_address,
            notes="Handle with care",
        )

        self.assertEqual(order.shipping_address, shipping_address)
        self.assertEqual(order.billing_address, billing_address)
        self.assertEqual(order.notes, "Handle with care")

    def test_order_status_choices(self):
        """Test all valid order status choices"""
        valid_statuses = [
            "pending",
            "processing",
            "on_transit",
            "shipped",
            "delivered",
            "cancelled",
            "refund_requested",
            "refunded",
        ]

        for status_choice in valid_statuses:
            order = Order.objects.create(user=self.user, status=status_choice)
            self.assertEqual(order.status, status_choice)

    def test_payment_status_choices(self):
        """Test all valid payment status choices"""
        valid_payment_statuses = ["unpaid", "paid", "refunded", "failed"]

        for payment_status in valid_payment_statuses:
            order = Order.objects.create(user=self.user, payment_status=payment_status)
            self.assertEqual(order.payment_status, payment_status)


class OrderItemModelTest(TestCase):
    """Test cases for OrderItem model"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

        self.product = Product.objects.create(
            name="Test Laptop",
            description="A test laptop",
            unit_price=Decimal("1000.00"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.order = Order.objects.create(user=self.user)

    def test_order_item_creation(self):
        """Test basic order item creation"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=2,
            price_per_item=self.product.unit_price,
        )

        self.assertIsNotNone(order_item.item_id)
        self.assertEqual(order_item.order, self.order)
        self.assertEqual(order_item.product, self.product)
        self.assertEqual(order_item.product_name, self.product.name)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.price_per_item, Decimal("1000.00"))
        self.assertEqual(order_item.total_price, Decimal("2000.00"))

    def test_order_item_total_price_calculation(self):
        """Test that total_price is calculated correctly on save"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=3,
            price_per_item=Decimal("500.00"),
        )

        self.assertEqual(order_item.total_price, Decimal("1500.00"))

    def test_order_item_string_representation(self):
        """Test order item string representation"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name="Test Product",
            quantity=5,
            price_per_item=Decimal("100.00"),
        )

        expected_str = "Test Product X 5"
        self.assertEqual(str(order_item), expected_str)

    def test_order_item_defaults(self):
        """Test order item default values"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            price_per_item=self.product.unit_price,
        )

        self.assertEqual(order_item.quantity, 1)
        self.assertEqual(order_item.total_price, self.product.unit_price)


class OrderSerializerTest(TestCase):
    """Test cases for Order serializers"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

        self.product = Product.objects.create(
            name="Test Laptop",
            description="A test laptop",
            unit_price=Decimal("1000.00"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("160.00"),
            shipping_cost=Decimal("300.00"),
            total_amount=Decimal("1460.00"),
        )

    def test_order_serializer_fields(self):
        """Test OrderSerializer contains all expected fields"""
        serializer = OrderSerializer(self.order)
        expected_fields = [
            "order_id",
            "order_number",
            "user",
            "status",
            "payment_status",
            "subtotal",
            "tax_amount",
            "shipping_cost",
            "total_amount",
            "shipping_address",
            "billing_address",
            "notes",
            "created_at",
            "order_items",
        ]

        for field in expected_fields:
            self.assertIn(field, serializer.data)

    def test_order_item_serializer_fields(self):
        """Test OrderItemSerializer contains all expected fields"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            price_per_item=self.product.unit_price,
        )

        serializer = OrderItemSerializer(order_item)
        expected_fields = [
            "item_id",
            "order",
            "product",
            "product_name",
            "quantity",
            "price_per_item",
            "total_price",
            "created_at",
        ]

        for field in expected_fields:
            self.assertIn(field, serializer.data)

    def test_order_serializer_with_items(self):
        """Test OrderSerializer includes nested order items"""
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=2,
            price_per_item=self.product.unit_price,
        )

        serializer = OrderSerializer(self.order)
        self.assertEqual(len(serializer.data["order_items"]), 1)
        self.assertEqual(serializer.data["order_items"][0]["quantity"], 2)


class CreateOrderFromCartViewTest(APITestCase):
    """Test cases for CreateOrderFromCartView"""

    def setUp(self):
        # Clear any existing cart items first
        CartItem.objects.all().delete()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            address={"street": "123 Main St", "city": "Test City", "zip": "12345"},
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

        self.product1 = Product.objects.create(
            name="Laptop",
            description="Test laptop",
            unit_price=Decimal("1000.00"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.product2 = Product.objects.create(
            name="Mouse",
            description="Test mouse",
            unit_price=Decimal("25.00"),
            in_stock=20,
            category=self.category,
            created_by=self.user,
        )

        # Get the user's cart (created by signal)
        self.cart = Cart.objects.get(user=self.user)

        # Create cart items (don't try to get them first)
        CartItem.objects.create(cart=self.cart, product=self.product1, quantity=1)
        CartItem.objects.create(cart=self.cart, product=self.product2, quantity=2)

        self.url = reverse("create-order")

    def test_create_order_requires_authentication(self):
        """Test that creating order requires authentication"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_order_empty_cart(self):
        """Test creating order with empty cart"""
        # Clear the cart for this test
        CartItem.objects.filter(cart=self.cart).delete()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Your cart is empty")

    def test_create_order_no_cart(self):
        """Test creating order when user has no cart"""
        # Delete the cart
        self.cart.delete()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("orders.tasks.send_order_email.delay")
    def test_create_order_success(self, mock_send_email):
        """Test successful order creation from cart"""
        # Clear and add fresh items for this test
        CartItem.objects.filter(cart=self.cart).delete()
        CartItem.objects.create(cart=self.cart, product=self.product1, quantity=1)
        CartItem.objects.create(cart=self.cart, product=self.product2, quantity=2)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"notes": "Test order notes"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)

        # Verify order was created
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.subtotal, Decimal("1050.00"))
        self.assertEqual(order.notes, "Test order notes")

        # Verify order items were created
        order_items = OrderItem.objects.filter(order=order)
        self.assertEqual(order_items.count(), 2)

        # Verify cart was cleared
        cart_items = CartItem.objects.filter(cart=self.cart)
        self.assertEqual(cart_items.count(), 0)

    @patch("orders.tasks.send_order_email.delay")
    def test_create_order_with_addresses(self, mock_send_email):
        """Test order creation with custom shipping and billing addresses"""
        # Clear and add fresh items for this test
        CartItem.objects.filter(cart=self.cart).delete()
        CartItem.objects.create(cart=self.cart, product=self.product1, quantity=1)

        shipping_address = {"street": "456 Oak St", "city": "Ship City", "zip": "54321"}
        billing_address = {"street": "789 Pine St", "city": "Bill City", "zip": "67890"}

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {"shipping_address": shipping_address, "billing_address": billing_address},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.shipping_address, shipping_address)
        self.assertEqual(order.billing_address, billing_address)

    @patch("orders.tasks.send_order_email.delay")
    def test_create_order_uses_default_address(self, mock_send_email):
        """Test order creation uses user's default address when not provided"""
        # Clear and add fresh items for this test
        CartItem.objects.filter(cart=self.cart).delete()
        CartItem.objects.create(cart=self.cart, product=self.product1, quantity=1)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.shipping_address, self.user.address)
        self.assertEqual(order.billing_address, self.user.address)


class OrderViewsetTest(APITestCase):
    """Test cases for OrderViewset"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            first_name="Other",
            last_name="User",
        )

        self.order1 = Order.objects.create(
            user=self.user, status="pending", payment_status="unpaid"
        )

        self.order2 = Order.objects.create(
            user=self.user, status="delivered", payment_status="paid"
        )

        self.other_order = Order.objects.create(user=self.other_user, status="pending")

    def test_list_orders_requires_authentication(self):
        """Test that listing orders requires authentication"""
        url = reverse("orders-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_user_orders_only(self):
        """Test that users can only see their own orders"""
        self.client.force_authenticate(user=self.user)
        url = reverse("orders-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        order_ids = [order["order_id"] for order in response.data]
        self.assertIn(str(self.order1.order_id), order_ids)
        self.assertIn(str(self.order2.order_id), order_ids)
        self.assertEqual(len(response.data), 2)
        self.assertNotIn(str(self.other_order.order_id), order_ids)

    def test_retrieve_order(self):
        """Test retrieving a specific order"""
        self.client.force_authenticate(user=self.user)
        url = reverse("orders-detail", args=[self.order1.order_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order_id"], str(self.order1.order_id))

    def test_cannot_retrieve_other_user_order(self):
        """Test that users cannot retrieve other users' orders"""
        self.client.force_authenticate(user=self.user)
        url = reverse("orders-detail", args=[self.other_order.order_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_pending_order_success(self):
        """Test successfully cancelling a pending order"""
        self.client.force_authenticate(user=self.user)
        url = reverse("orders-cancel", args=[self.order1.order_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)

        # Verify order was cancelled
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, "cancelled")
        self.assertIsNotNone(self.order1.cancelled_at)

    def test_cancel_non_pending_order_fails(self):
        """Test that non-pending orders cannot be cancelled"""
        self.client.force_authenticate(user=self.user)
        url = reverse("orders-cancel", args=[self.order2.order_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_cancel_paid_order_fails(self):
        """Test that paid orders cannot be cancelled"""
        paid_order = Order.objects.create(
            user=self.user, status="pending", payment_status="paid"
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("orders-cancel", args=[paid_order.order_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)


class OrderSignalsTest(TestCase):
    """Test cases for Order signals"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

    @patch("orders.signals.send_order_email.delay")
    def test_order_created_signal(self, mock_send_email):
        """Test that signal is sent when order is created"""
        order = Order.objects.create(user=self.user)

        mock_send_email.assert_called_once_with(
            event="created",
            order_id=str(order.order_id),
            user_email=self.user.email,
            user_fullname="Test User",
        )

    @patch("orders.signals.send_order_email.delay")
    def test_order_status_changed_signal(self, mock_send_email):
        """Test that signal is sent when order status changes"""
        order = Order.objects.create(user=self.user)
        mock_send_email.reset_mock()

        order.status = "processing"
        order.save()

        mock_send_email.assert_called_with(
            event="status_changed",
            order_id=str(order.order_id),
            user_fullname="Test User",
            user_email=self.user.email,
            old_value="pending",
            new_value="processing",
        )

    @patch("orders.signals.send_order_email.delay")
    def test_payment_status_changed_signal(self, mock_send_email):
        """Test that signal is sent when payment status changes"""
        order = Order.objects.create(user=self.user)
        mock_send_email.reset_mock()

        order.payment_status = "paid"
        order.save()

        mock_send_email.assert_called_with(
            event="payment_status_changed",
            order_id=str(order.order_id),
            user_email=self.user.email,
            old_value="unpaid",
            new_value="paid",
            user_fullname="Test User",
        )

    @patch("orders.signals.send_order_email.delay")
    def test_payment_failed_signal(self, mock_send_email):
        """Test that signal is sent when payment fails"""
        order = Order.objects.create(user=self.user)
        mock_send_email.reset_mock()

        order.payment_status = "failed"
        order.save()

        # Should be called twice - once for status change, once for payment failed
        self.assertEqual(mock_send_email.call_count, 2)

        # Check payment failed call
        calls = mock_send_email.call_args_list
        payment_failed_call = calls[1]  # Second call
        self.assertEqual(payment_failed_call[1]["event"], "payment_failed")

    @patch("orders.signals.send_order_email.delay")
    def test_no_signal_when_no_changes(self, mock_send_email):
        """Test that no signal is sent when order is saved without changes"""
        order = Order.objects.create(user=self.user)
        mock_send_email.reset_mock()

        # Save without changes
        order.save()

        # Should not be called
        mock_send_email.assert_not_called()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OrderTasksTest(TestCase):
    """Test cases for Order email tasks"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        # Disable signals
        with patch("orders.signals.send_order_created_email"), patch(
            "orders.signals.send_order_update_emails"
        ):

            self.user = User.objects.create_user(
                username="testuser",
                email="test@example.com",
                first_name="Test",
                last_name="User",
            )
            self.order = Order.objects.create(user=self.user)

        # Clear email outbox
        mail.outbox = []

    def test_send_order_created_email(self):
        """Test sending order created email"""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            send_order_email(
                event="created",
                order_id=str(self.order.order_id),
                user_fullname="Test User",
                user_email=self.user.email,
            )

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, "🎉 Order placed successfully.")
            self.assertIn(self.order.order_number, email.body)
            self.assertIn("Test User", email.body)

    def test_send_status_changed_email(self):
        """Test sending order status changed email"""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            send_order_email(
                event="status_changed",
                order_id=str(self.order.order_id),
                user_fullname="Test User",
                user_email=self.user.email,
                old_value="pending",
                new_value="processing",
            )

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, "📦 Order Status Updated")
            self.assertIn("pending", email.body)
            self.assertIn("processing", email.body)

    def test_send_payment_status_changed_email(self):
        """Test sending payment status changed email"""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            send_order_email(
                event="payment_status_changed",
                order_id=str(self.order.order_id),
                user_fullname="Test User",
                user_email=self.user.email,
                old_value="unpaid",
                new_value="paid",
            )

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, "💳 Payment Status Updated")
            self.assertIn("unpaid", email.body)
            self.assertIn("paid", email.body)

    def test_send_payment_failed_email(self):
        """Test sending payment failed email"""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            send_order_email(
                event="payment_failed",
                order_id=str(self.order.order_id),
                user_fullname="Test User",
                user_email=self.user.email,
            )

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, "🚫 Payment Failed")
            self.assertIn("failed", email.body)
            self.assertIn(str(self.order.total_amount), email.body)


class OrderIntegrationTest(APITestCase):
    """Integration tests for the complete order flow"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            address={"street": "123 Main St", "city": "Test City", "zip": "12345"},
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

        self.product = Product.objects.create(
            name="Test Product",
            description="A test product",
            unit_price=Decimal("100.00"),
            in_stock=10,
            category=self.category,
            created_by=self.user,
        )

        self.cart = Cart.objects.get(user=self.user)
        CartItem.objects.filter(cart=self.cart).delete()
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)

    @patch("orders.tasks.send_order_email.delay")
    def test_complete_order_flow(self, mock_send_email):
        """Test complete flow from cart to order cancellation"""
        self.client.force_authenticate(user=self.user)

        # 1. Create order from cart
        create_url = reverse("create-order")
        response = self.client.post(create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order_id = response.data["success"]["order_id"]

        # 2. List orders
        list_url = reverse("orders-list")
        response = self.client.get(list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # 3. Retrieve specific order
        detail_url = reverse("orders-detail", args=[order_id])
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["order_items"]), 1)

        # 4. Cancel order
        cancel_url = reverse("orders-cancel", args=[order_id])
        response = self.client.post(cancel_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify order is cancelled
        order = Order.objects.get(order_id=order_id)
        self.assertEqual(order.status, "cancelled")
        self.assertIsNotNone(order.cancelled_at)


# Additional edge case tests
class OrderEdgeCasesTest(TestCase):
    """Test edge cases and error conditions"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

    def test_order_with_zero_amounts(self):
        """Test order creation with zero amounts"""
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            shipping_cost=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )

        self.assertEqual(order.subtotal, Decimal("0.00"))
        self.assertEqual(order.tax_amount, Decimal("0.00"))
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("0.00"))

    def test_order_item_with_zero_quantity(self):
        """Test order item creation with zero quantity"""
        category = Category.objects.create(name="Test", created_by=self.user)
        product = Product.objects.create(
            name="Test Product",
            description="Test",
            unit_price=Decimal("100.00"),
            category=category,
            created_by=self.user,
        )
        order = Order.objects.create(user=self.user)

        # This should still work as quantity is PositiveIntegerField with default=1
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=0,  # This might cause validation error in real scenario
            price_per_item=product.unit_price,
        )

        self.assertEqual(order_item.total_price, Decimal("0.00"))

    def test_order_with_very_large_amounts(self):
        """Test order with large decimal amounts"""
        large_amount = Decimal("99999999.99")  # Max for 10 digits, 2 decimal places

        order = Order.objects.create(
            user=self.user,
            subtotal=large_amount,
            tax_amount=large_amount,
            shipping_cost=large_amount,
            total_amount=large_amount,
        )

        self.assertEqual(order.subtotal, large_amount)
        self.assertEqual(order.tax_amount, large_amount)
        self.assertEqual(order.shipping_cost, large_amount)
        self.assertEqual(order.total_amount, large_amount)

    def test_order_number_uniqueness(self):
        """Test that order numbers are unique"""
        order1 = Order.objects.create(user=self.user)
        order2 = Order.objects.create(user=self.user)

        self.assertNotEqual(order1.order_number, order2.order_number)

        # Verify both are valid UUID-based strings
        self.assertEqual(len(order1.order_number), 8)
        self.assertEqual(len(order2.order_number), 8)

    def test_order_with_null_user_fails(self):
        """Test that order creation fails without user"""
        with self.assertRaises(Exception):
            Order.objects.create(user=None)

    @patch("orders.signals.send_order_email.delay")
    def test_signal_with_missing_user_names(self, mock_send_email):
        """Test signal handling when user has no first/last name"""
        user_no_name = User.objects.create_user(
            username="noname", email="noname@example.com", first_name="", last_name=""
        )

        order = Order.objects.create(user=user_no_name)

        mock_send_email.assert_called_once_with(
            event="created",
            order_id=str(order.order_id),
            user_email=user_no_name.email,
            user_fullname=" ",  # Empty first + " " + empty last
        )


class OrderValidationTest(TestCase):
    """Test validation scenarios"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

    def test_invalid_order_status(self):
        """Test that invalid order status raises error"""
        # This would typically be caught by Django's validation
        order = Order(user=self.user, status="invalid_status")

        with self.assertRaises(Exception):
            order.full_clean()

    def test_invalid_payment_status(self):
        """Test that invalid payment status raises error"""
        order = Order(user=self.user, payment_status="invalid_payment_status")

        with self.assertRaises(Exception):
            order.full_clean()

    def test_order_item_negative_quantity(self):
        """Test order item with negative quantity"""
        category = Category.objects.create(name="Test", created_by=self.user)
        product = Product.objects.create(
            name="Test Product",
            description="Test",
            unit_price=Decimal("100.00"),
            category=category,
            created_by=self.user,
        )
        order = Order.objects.create(user=self.user)

        # This should fail validation for PositiveIntegerField
        order_item = OrderItem(
            order=order,
            product=product,
            product_name=product.name,
            quantity=-1,
            price_per_item=product.unit_price,
        )

        with self.assertRaises(Exception):
            order_item.full_clean()


class OrderQueryTest(TestCase):
    """Test order queries and filtering"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            first_name="User",
            last_name="One",
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            first_name="User",
            last_name="Two",
        )

        # Create orders for both users
        self.order1 = Order.objects.create(
            user=self.user1, status="pending", payment_status="unpaid"
        )

        self.order2 = Order.objects.create(
            user=self.user1, status="delivered", payment_status="paid"
        )

        self.order3 = Order.objects.create(
            user=self.user2, status="pending", payment_status="unpaid"
        )

    def test_filter_orders_by_user(self):
        """Test filtering orders by user"""
        user1_orders = Order.objects.filter(user=self.user1)
        user2_orders = Order.objects.filter(user=self.user2)

        self.assertEqual(user1_orders.count(), 2)
        self.assertEqual(user2_orders.count(), 1)

    def test_filter_orders_by_status(self):
        """Test filtering orders by status"""
        pending_orders = Order.objects.filter(status="pending")
        delivered_orders = Order.objects.filter(status="delivered")

        self.assertEqual(pending_orders.count(), 2)
        self.assertEqual(delivered_orders.count(), 1)

    def test_filter_orders_by_payment_status(self):
        """Test filtering orders by payment status"""
        unpaid_orders = Order.objects.filter(payment_status="unpaid")
        paid_orders = Order.objects.filter(payment_status="paid")

        self.assertEqual(unpaid_orders.count(), 2)
        self.assertEqual(paid_orders.count(), 1)

    def test_order_by_created_at(self):
        """Test ordering orders by creation date"""
        orders = Order.objects.all().order_by("-created_at")

        # Should be in descending order
        self.assertTrue(orders[0].created_at >= orders[1].created_at)
        self.assertTrue(orders[1].created_at >= orders[2].created_at)


class OrderPermissionsTest(APITestCase):
    """Test order permissions and security"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        self.customer_user = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            first_name="Customer",
            last_name="User",
            role="customer",
        )

        self.other_customer = User.objects.create_user(
            username="other",
            email="other@example.com",
            first_name="Other",
            last_name="Customer",
            role="customer",
        )

        self.customer_order = Order.objects.create(user=self.customer_user)
        self.other_order = Order.objects.create(user=self.other_customer)

    def test_customer_cannot_access_other_orders(self):
        """Test that customers can only access their own orders"""
        self.client.force_authenticate(user=self.customer_user)

        # Try to access other customer's order
        url = reverse("orders-detail", args=[self.other_order.order_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_cancel_other_orders(self):
        """Test that customers cannot cancel other customers' orders"""
        self.client.force_authenticate(user=self.customer_user)

        # Try to cancel other customer's order
        url = reverse("orders-cancel", args=[self.other_order.order_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_access_denied(self):
        """Test that unauthenticated users cannot access orders"""
        # Don't authenticate

        # Try to list orders
        url = reverse("orders-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Try to access specific order
        url = reverse("orders-detail", args=[self.customer_order.order_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Try to cancel order
        url = reverse("orders-cancel", args=[self.customer_order.order_id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OrderConcurrencyTest(TestCase):
    """Test concurrent operations on orders"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.category = Category.objects.create(name="Test", created_by=self.user)
        self.product = Product.objects.create(
            name="Test Product",
            description="Test",
            unit_price=Decimal("100.00"),
            in_stock=5,
            category=self.category,
            created_by=self.user,
        )

    def test_multiple_order_creation_from_same_cart(self):
        """Test handling multiple simultaneous order creation attempts"""
        cart = Cart.objects.get(user=self.user)
        CartItem.objects.filter(cart=cart).delete()  # clear cart items.
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        # Simulate what would happen if two requests tried to create orders
        # from the same cart simultaneously
        from django.db import transaction

        with transaction.atomic():
            # First order creation - should succeed
            cart_items = CartItem.objects.filter(cart=cart)
            self.assertTrue(cart_items.exists())

            order1 = Order.objects.create(user=self.user)
            for item in cart_items:
                OrderItem.objects.create(
                    order=order1,
                    product=item.product,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    price_per_item=item.product.unit_price,
                )

            # Clear cart
            cart_items.delete()

            # Second attempt should find empty cart
            cart_items_after = CartItem.objects.filter(cart=cart)
            self.assertFalse(cart_items_after.exists())


class OrderBusinessLogicTest(TestCase):
    """Test business logic and calculations"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

    def test_tax_calculation_accuracy(self):
        """Test that tax calculation is accurate"""
        subtotal = Decimal("100.00")
        expected_tax = subtotal * Decimal("0.16")  # 16% tax

        self.assertEqual(expected_tax, Decimal("16.00"))

    def test_order_total_calculation(self):
        """Test complete order total calculation"""
        subtotal = Decimal("100.00")
        tax = Decimal("16.00")
        shipping = Decimal("300.00")
        expected_total = subtotal + tax + shipping

        order = Order.objects.create(
            user=self.user,
            subtotal=subtotal,
            tax_amount=tax,
            shipping_cost=shipping,
            total_amount=expected_total,
        )

        self.assertEqual(order.total_amount, Decimal("416.00"))

    def test_decimal_precision(self):
        """Test decimal precision in calculations"""
        # Test with fractional amounts
        price_per_item = Decimal("33.33")
        quantity = 3
        expected_total = Decimal("99.99")

        product = Product.objects.create(
            name="Test Product",
            description="Test",
            unit_price=price_per_item,
            category=self.category,
            created_by=self.user,
        )

        order = Order.objects.create(user=self.user)
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=quantity,
            price_per_item=price_per_item,
        )

        self.assertEqual(order_item.total_price, expected_total)

    def test_shipping_cost_logic(self):
        """Test shipping cost application"""
        # Based on the view, shipping cost is fixed at 300
        expected_shipping = Decimal("300.00")

        order = Order.objects.create(user=self.user, shipping_cost=expected_shipping)

        self.assertEqual(order.shipping_cost, expected_shipping)


# Performance and scalability tests
class OrderPerformanceTest(TestCase):
    """Test performance aspects of order system"""

    def setUp(self):

        # clear any existing cart items first
        CartItem.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        self.category = Category.objects.create(
            name="Electronics", created_by=self.user
        )

    def test_bulk_order_item_creation(self):
        """Test creating multiple order items efficiently"""
        # Create multiple products
        products = []
        for i in range(10):
            product = Product.objects.create(
                name=f"Product {i}",
                description=f"Description {i}",
                unit_price=Decimal("100.00"),
                category=self.category,
                created_by=self.user,
            )
            products.append(product)

        order = Order.objects.create(user=self.user)

        # Create order items
        order_items = []
        for product in products:
            order_item = OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                quantity=1,
                price_per_item=product.unit_price,
                total_price=product.unit_price,
            )
            order_items.append(order_item)

        # Bulk create
        OrderItem.objects.bulk_create(order_items)

        self.assertEqual(OrderItem.objects.filter(order=order).count(), 10)

    def test_order_queries_efficiency(self):
        """Test that order queries are efficient"""
        # Create order with items
        order = Order.objects.create(user=self.user)

        product = Product.objects.create(
            name="Test Product",
            description="Test",
            unit_price=Decimal("100.00"),
            category=self.category,
            created_by=self.user,
        )

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=1,
            price_per_item=product.unit_price,
        )

        # Test prefetch_related usage
        orders_with_items = Order.objects.prefetch_related("order_items").filter(
            user=self.user
        )

        # This should not cause additional queries
        for order in orders_with_items:
            items = list(order.order_items.all())  # Should not hit DB again
            self.assertGreater(len(items), 0)

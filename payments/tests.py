import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order
from payments.models import Payment
from payments.services.chapa import ChapaProvider

User = get_user_model()

# Test settings override
TEST_SETTINGS = {
    "CHAPA_SECRET_KEY": "test-secret-key",
    "CHAPA_CALLBACK_URL": "http://test.com/callback",
    "PAYMENT_CALLBACK_URLS": {
        "chapa": "http://test.com",
    },
}


class ChapaProviderTests(TestCase):
    """Enhanced tests for ChapaProvider with better coverage"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal("100.00"), total_amount=Decimal("125.00")
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="chapa",
            amount=Decimal("125.00"),
            currency="ETB",
            transaction_ref=str(uuid.uuid4()),
        )
        self.provider = ChapaProvider()

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_initiate_payment_success_with_callback(self, mock_post):
        """Test successful payment initiation with custom callback URL"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_response

        custom_callback = "http://custom-callback.com"
        result = self.provider.initiate_payment(
            payment=self.payment, callback_url=custom_callback
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["checkout_url"], "https://checkout.chapa.co/test")

        # Verify callback URL was used in request
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["callback_url"], custom_callback)

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_initiate_payment_with_missing_user_data(self, mock_post):
        """Test payment initiation when user has missing name fields"""
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save()

        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_response

        result = self.provider.initiate_payment(payment=self.payment)
        self.assertTrue(result["success"])

        # Verify empty strings were sent for missing names
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["first_name"], "")
        self.assertEqual(call_args[1]["json"]["last_name"], "")

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_initiate_payment_with_api_error_response(self, mock_post):
        """Test handling of API error responses"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "failed",
            "message": "Invalid currency",
        }
        mock_post.return_value = mock_response

        result = self.provider.initiate_payment(payment=self.payment)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid currency")

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_initiate_payment_with_invalid_json_response(self, mock_post):
        """Test handling of invalid JSON responses"""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        result = self.provider.initiate_payment(payment=self.payment)
        self.assertFalse(result["success"])
        self.assertIn("Invalid JSON", result["error"])

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.get")
    def test_verify_payment_with_success_status(self, mock_get):
        """Test verification with successful payment status"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": self.payment.transaction_ref,
                "amount": "125.00",
            },
        }
        mock_get.return_value = mock_response

        result = self.provider.verify_payment(
            transaction_ref=self.payment.transaction_ref
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["amount"], "125.00")

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.get")
    def test_verify_payment_with_failed_status(self, mock_get):
        """Test verification with failed payment status"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "failed",
            "data": {"status": "failed", "message": "Payment declined"},
        }
        mock_get.return_value = mock_response

        result = self.provider.verify_payment(
            transaction_ref=self.payment.transaction_ref
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["data"]["message"], "Payment declined")

    def test_handle_webhook_with_alternative_tx_ref_key(self):
        """Test webhook handling with alternative transaction reference key"""
        mock_request = Mock()
        mock_request.data = {
            "txRef": "alt-tx-ref-123",  # Alternative key
            "status": "success",
        }

        result = self.provider.handle_webhook(mock_request)
        self.assertEqual(result["transaction_ref"], "alt-tx-ref-123")

    def test_handle_webhook_with_missing_tx_ref(self):
        """Test webhook handling when transaction reference is missing"""
        mock_request = Mock()
        mock_request.data = {"status": "success"}  # No tx_ref

        result = self.provider.handle_webhook(mock_request)
        self.assertIsNone(result["transaction_ref"])


class PaymentViewIntegrationTests(APITestCase):
    """Integration tests covering the full payment flow"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal("100.00"), total_amount=Decimal("125.00")
        )
        self.url = reverse("initiate-payment", kwargs={"order_id": self.order.order_id})

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    @patch("payments.services.chapa.requests.get")
    def test_complete_payment_flow(self, mock_get, mock_post):
        """Test complete payment flow from initiation to verification"""
        # Mock initiate payment response
        mock_init_response = Mock()
        mock_init_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_init_response

        # Mock verify payment response
        mock_verify_response = Mock()
        mock_verify_response.json.return_value = {
            "status": "success",
            "data": {"status": "success", "amount": 125.00},
        }
        mock_get.return_value = mock_verify_response

        self.client.force_authenticate(user=self.user)

        # Step 1: Initiate payment
        initiate_response = self.client.post(
            self.url, {"provider": "chapa"}, format="json"
        )
        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)

        # Get created payment
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, "processing")

        # Step 2: Verify payment (simulate callback)
        verify_url = reverse("provider-verify", kwargs={"provider": "chapa"})
        verify_response = self.client.get(
            verify_url, {"trx_ref": payment.transaction_ref}
        )
        self.assertEqual(verify_response.status_code, 302)

        # Verify final states
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, "success")
        self.assertEqual(self.order.payment_status, "paid")

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_payment_retry_after_failure(self, mock_post):
        """Test payment retry after initial failure"""
        # Create a failed payment
        failed_payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="chapa",
            amount=Decimal("125.00"),
            currency="ETB",
            transaction_ref="failed-tx-123",
            status="failed",
        )

        # Mock successful response for retry
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/retry"},
        }
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"provider": "chapa"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify existing payment was updated
        failed_payment.refresh_from_db()
        self.assertEqual(failed_payment.status, "processing")
        self.assertNotEqual(failed_payment.transaction_ref, "failed-tx-123")

    def test_payment_initiation_with_invalid_order_state(self):
        """Test payment initiation with cancelled order"""
        self.order.status = "cancelled"
        self.order.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"provider": "chapa"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancelled", response.data["error"])

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.post")
    def test_concurrent_payment_attempts(self, mock_post):
        """Test handling of concurrent payment attempts"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)

        # First request - should succeed
        response1 = self.client.post(self.url, {"provider": "chapa"})
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request - should fail (payment already in progress)
        response2 = self.client.post(self.url, {"provider": "chapa"})
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment in progress", response2.data["error"])


class ProviderVerifyViewTests(APITestCase):
    """Enhanced tests for ProviderVerifyView"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.order = Order.objects.create(
            user=self.user, total_amount=Decimal("125.00")
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="chapa",
            amount=Decimal("125.00"),
            currency="ETB",
            transaction_ref="test-tx-123",
            status="processing",
        )
        self.url = reverse("provider-verify", kwargs={"provider": "chapa"})

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.get")
    def test_webhook_verification(self, mock_get):
        """Test webhook verification via POST"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"status": "success"},
        }
        mock_get.return_value = mock_response

        response = self.client.post(
            self.url, {"trx_ref": "test-tx-123"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify payment and order were updated
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, "success")
        self.assertEqual(self.order.payment_status, "paid")

    @override_settings(**TEST_SETTINGS)
    @patch("payments.services.chapa.requests.get")
    def test_webhook_verification_with_failed_payment(self, mock_get):
        """Test webhook verification for failed payment"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "failed",
            "data": {"status": "failed"},
        }
        mock_get.return_value = mock_response

        response = self.client.post(
            self.url, {"trx_ref": "test-tx-123"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify payment and order were marked as failed
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.order.payment_status, "failed")

    def test_webhook_with_invalid_provider(self):
        """Test webhook with invalid payment provider"""
        invalid_url = reverse("provider-verify", kwargs={"provider": "invalid"})
        response = self.client.post(
            invalid_url, {"trx_ref": "test-tx-123"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown provider", response.data["error"])

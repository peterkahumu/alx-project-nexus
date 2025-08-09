# tests/test_integration.py
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from payments.models import Payment
from payments.services.chapa import ChapaProvider
from payments.services.registry import _PROVIDERS, register

User = get_user_model()


class PaymentIntegrationTests(TestCase):
    """Integration tests for the complete payment flow"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            first_name="Test2",
            last_name="User2",
            password="testpass123",
        )

        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("15.00"),
            shipping_cost=Decimal("10.00"),
            total_amount=Decimal("125.00"),
            status="pending",
            payment_status="unpaid",
        )

        # Clear registry and register fresh providers for each test
        _PROVIDERS.clear()

    def tearDown(self):
        """Clean up after each test"""
        _PROVIDERS.clear()

    @patch("payments.services.chapa.requests.post")
    @patch("payments.services.chapa.requests.get")
    @patch("payments.services.chapa.settings")
    def test_complete_chapa_payment_flow_success(
        self, mock_settings, mock_get, mock_post
    ):
        """Test complete Chapa payment flow from initiation to successful verification"""
        # Setup mocks
        mock_settings.CHAPA_SECRET_KEY = "test-secret-key"
        mock_settings.CHAPA_CALLBACK_URL = "http://test.com/callback"
        mock_settings.PAYMENT_CALLBACK_URLS = {"chapa": "http://test.com"}

        # Mock successful initiate payment response
        mock_init_response = Mock()
        mock_init_response.json.return_value = {
            "status": "success",
            "data": {
                "checkout_url": "https://checkout.chapa.co/checkout/test-123",
                "reference": "chapa-tx-123",
            },
        }
        mock_post.return_value = mock_init_response

        # Mock successful verify payment response
        mock_verify_response = Mock()
        mock_verify_response.json.return_value = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": "test-tx-ref",
                "amount": 125.00,
                "currency": "ETB",
                "reference": "chapa-tx-123",
            },
        }
        mock_get.return_value = mock_verify_response

        # Register Chapa provider
        chapa_provider = ChapaProvider()
        register("chapa", chapa_provider)

        self.client.force_authenticate(user=self.user)

        # Step 1: Verify initial states
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.payment_status, "unpaid")
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

        # Step 2: Initiate payment
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        initiate_response = self.client.post(initiate_url, {"provider": "chapa"})

        # Verify initiate response
        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)
        self.assertIn("checkout_url", initiate_response.data)
        self.assertEqual(
            initiate_response.data["checkout_url"],
            "https://checkout.chapa.co/checkout/test-123",
        )

        # Verify payment record was created
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, "processing")
        self.assertEqual(payment.provider, "chapa")
        self.assertEqual(payment.amount, Decimal("125.00"))
        self.assertEqual(payment.user, self.user)
        self.assertIsNotNone(payment.transaction_ref)

        # Verify API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0], "https://api.chapa.co/v1/transaction/initialize"
        )

        payload = call_args[1]["json"]
        self.assertEqual(payload["amount"], "125.00")
        self.assertEqual(payload["currency"], "ETB")
        self.assertEqual(payload["email"], "test@example.com")
        self.assertEqual(payload["first_name"], "Test")
        self.assertEqual(payload["last_name"], "User")

        # Step 3: Simulate callback/verification (GET request)
        verify_url = reverse("provider-verify", kwargs={"provider": "chapa"})
        verify_response = self.client.get(
            verify_url, {"trx_ref": payment.transaction_ref}
        )

        # Should redirect to success page
        self.assertEqual(verify_response.status_code, 302)
        self.assertIn("payment-result?status=success", verify_response.url)

        # Verify verification API call
        mock_get.assert_called_once_with(
            f"https://api.chapa.co/v1/transaction/verify/{payment.transaction_ref}",
            headers={"Authorization": "Bearer test-secret-key"},
            timeout=15,
        )

        # Step 4: Verify final states
        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, "success")
        self.assertEqual(
            payment.provider_response, mock_verify_response.json.return_value
        )
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.status, "processing")

    @patch("payments.services.chapa.requests.post")
    @patch("payments.services.chapa.requests.get")
    @patch("payments.services.chapa.settings")
    def test_complete_payment_flow_with_failure(
        self, mock_settings, mock_get, mock_post
    ):
        """Test complete payment flow ending in failure"""
        # Setup mocks
        mock_settings.CHAPA_SECRET_KEY = "test-secret-key"
        mock_settings.CHAPA_CALLBACK_URL = "http://test.com/callback"
        mock_settings.PAYMENT_CALLBACK_URLS = {"chapa": "http://test.com"}

        # Mock successful initiate
        mock_init_response = Mock()
        mock_init_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_init_response

        # Mock failed verify
        mock_verify_response = Mock()
        mock_verify_response.json.return_value = {
            "status": "failed",
            "message": "Payment was declined by bank",
            "data": {"status": "failed"},
        }
        mock_get.return_value = mock_verify_response

        chapa_provider = ChapaProvider()
        register("chapa", chapa_provider)

        self.client.force_authenticate(user=self.user)

        # Initiate payment
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        initiate_response = self.client.post(initiate_url, {"provider": "chapa"})

        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)

        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, "processing")

        # Verify failed payment
        verify_url = reverse("provider-verify", kwargs={"provider": "chapa"})
        verify_response = self.client.get(
            verify_url, {"trx_ref": payment.transaction_ref}
        )

        # Should redirect to failure page
        self.assertEqual(verify_response.status_code, 302)
        self.assertIn("payment-result?status=failed", verify_response.url)

        # Verify final states
        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, "failed")
        self.assertEqual(self.order.payment_status, "failed")
        self.assertEqual(self.order.status, "pending")  # Should remain pending

    @patch("payments.services.chapa.requests.post")
    @patch("payments.services.chapa.requests.get")
    @patch("payments.services.chapa.settings")
    def test_webhook_vs_redirect_verification(self, mock_settings, mock_get, mock_post):
        """Test both webhook POST and redirect GET verification methods"""
        # Setup mocks
        mock_settings.CHAPA_SECRET_KEY = "test-secret-key"
        mock_settings.CHAPA_CALLBACK_URL = "http://test.com/callback"
        mock_settings.PAYMENT_CALLBACK_URLS = {"chapa": "http://test.com"}

        # Mock initiate response
        mock_init_response = Mock()
        mock_init_response.json.return_value = {
            "status": "success",
            "data": {"checkout_url": "https://checkout.chapa.co/test"},
        }
        mock_post.return_value = mock_init_response

        # Mock verify response
        mock_verify_response = Mock()
        mock_verify_response.json.return_value = {
            "status": "success",
            "data": {"status": "success", "amount": 125.00},
        }
        mock_get.return_value = mock_verify_response

        chapa_provider = ChapaProvider()
        register("chapa", chapa_provider)

        self.client.force_authenticate(user=self.user)

        # Initiate payment
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        self.client.post(initiate_url, {"provider": "chapa"})

        payment = Payment.objects.get(order=self.order)
        tx_ref = payment.transaction_ref

        # Test webhook verification (POST)
        verify_url = reverse("provider-verify", kwargs={"provider": "chapa"})
        webhook_response = self.client.post(
            verify_url,
            json.dumps({"trx_ref": tx_ref, "status": "success"}),
            content_type="application/json",
        )

        # Webhook should return JSON response, not redirect
        self.assertEqual(webhook_response.status_code, 200)
        webhook_data = webhook_response.json()
        self.assertEqual(webhook_data["status"], "success")
        self.assertIn("details", webhook_data)

        # Reset payment status for second test
        payment.status = "processing"
        payment.save()

        # Test redirect verification (GET)
        redirect_response = self.client.get(verify_url, {"trx_ref": tx_ref})

        # Redirect should redirect to result page
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn("payment-result", redirect_response.url)

    def test_payment_retry_flow(self):
        """Test complete flow for payment retry after failure"""
        # Create initial failed payment
        failed_payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="chapa",
            amount=Decimal("125.00"),
            currency="ETB",
            transaction_ref="failed-tx-123",
            status="failed",
        )

        # Mock provider for retry
        mock_provider = Mock()
        mock_provider.initiate_payment.return_value = {
            "success": True,
            "checkout_url": "https://test.com/retry-checkout",
            "payment_id": str(failed_payment.payment_id),
        }
        mock_provider.verify_payment.return_value = {
            "status": "success",
            "data": {"status": "success"},
        }
        register("chapa", mock_provider)

        self.client.force_authenticate(user=self.user)

        # Verify initial state
        self.assertEqual(failed_payment.status, "failed")
        self.assertEqual(self.order.payment_status, "unpaid")

        # Retry payment
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        retry_response = self.client.post(initiate_url, {"provider": "chapa"})

        # Should succeed
        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        self.assertIn("checkout_url", retry_response.data)

        # Verify same payment record was updated
        failed_payment.refresh_from_db()
        self.assertEqual(failed_payment.status, "processing")
        self.assertNotEqual(
            failed_payment.transaction_ref, "failed-tx-123"
        )  # New tx_ref

        # Verify only one payment exists
        payment_count = Payment.objects.filter(order=self.order).count()
        self.assertEqual(payment_count, 1)

        # Complete the retry by verifying
        verify_url = reverse("provider-verify", kwargs={"provider": "chapa"})
        verify_response = self.client.get(
            verify_url, {"trx_ref": failed_payment.transaction_ref}
        )

        self.assertEqual(verify_response.status_code, 302)
        self.assertIn("success", verify_response.url)

        # Final verification
        failed_payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(failed_payment.status, "success")
        self.assertEqual(self.order.payment_status, "paid")

    def test_multi_user_payment_isolation(self):
        """Test that users can only access their own payments and orders"""
        # Create orders for both users
        user2_order = Order.objects.create(
            user=self.user2,
            subtotal=Decimal("50.00"),
            total_amount=Decimal("50.00"),
            status="pending",
            payment_status="unpaid",
        )

        # Create payments for both users
        _ = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="test_provider",
            amount=Decimal("125.00"),
            currency="ETB",
            transaction_ref="user1-tx-123",
            status="processing",
        )

        _ = Payment.objects.create(
            order=user2_order,
            user=self.user2,
            provider="test_provider",
            amount=Decimal("50.00"),
            currency="ETB",
            transaction_ref="user2-tx-456",
            status="processing",
        )

        # Mock provider
        mock_provider = Mock()
        mock_provider.initiate_payment.return_value = {
            "success": True,
            "checkout_url": "https://test.com/checkout",
            "payment_id": str(uuid.uuid4()),
        }
        mock_provider.verify_payment.return_value = {
            "status": "success",
            "data": {"status": "success"},
        }
        register("test_provider", mock_provider)

        # Test user1 cannot access user2's order
        self.client.force_authenticate(user=self.user)

        user2_initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": user2_order.order_id}
        )
        response = self.client.post(user2_initiate_url, {"provider": "test_provider"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Test user1 can access their own order
        user1_initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        response = self.client.post(user1_initiate_url, {"provider": "test_provider"})
        # Should fail because payment already exists and is processing
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment in progress", response.data["error"])

        # Test webhook verification works for any user's payment (no auth required)
        verify_url = reverse("provider-verify", kwargs={"provider": "test_provider"})

        # User1's payment verification
        response = self.client.post(
            verify_url, {"trx_ref": "user1-tx-123"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # User2's payment verification
        response = self.client.post(
            verify_url, {"trx_ref": "user2-tx-456"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

    @patch("payments.services.chapa.requests.post")
    def test_payment_initiation_failure_handling(self, mock_post):
        """Test proper handling when payment initiation fails"""
        # Mock failed initiate response
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "failed",
            "message": "Invalid merchant configuration",
        }
        mock_post.return_value = mock_response

        chapa_provider = ChapaProvider()
        register("chapa", chapa_provider)

        self.client.force_authenticate(user=self.user)

        # Attempt payment initiation
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        response = self.client.post(initiate_url, {"provider": "chapa"})

        # Should return error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid merchant configuration", response.data["error"])

        # Payment should be created but marked as failed
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, "failed")
        self.assertEqual(payment.provider, "chapa")

        # Order should remain unpaid
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "unpaid")

    def test_verification_with_invalid_transaction_ref(self):
        """Test verification with non-existent transaction reference"""
        mock_provider = Mock()
        register("test_provider", mock_provider)

        verify_url = reverse("provider-verify", kwargs={"provider": "test_provider"})

        # Test with non-existent transaction reference
        response = self.client.get(verify_url, {"trx_ref": "non-existent-tx-ref"})

        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn("Payment not found", response_data["error"])

        # Provider's verify_payment should not be called
        mock_provider.verify_payment.assert_not_called()

    @override_settings(
        PAYMENT_CALLBACK_URLS={"test_provider": "https://test-callback.com"}
    )
    def test_order_state_transitions(self):
        """Test proper order state transitions during payment flow"""
        # Mock provider
        mock_provider = Mock()
        mock_provider.initiate_payment.return_value = {
            "success": True,
            "checkout_url": "https://test.com/checkout",
            "payment_id": str(uuid.uuid4()),
        }
        register("test_provider", mock_provider)

        self.client.force_authenticate(user=self.user)

        # Initial state
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.payment_status, "unpaid")

        # After payment initiation
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        self.client.post(initiate_url, {"provider": "test_provider"})
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, "processing")
        # Order status should remain unchanged until payment succeeds
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.payment_status, "unpaid")

        # Mock successful verification
        mock_provider.verify_payment.return_value = {
            "status": "success",
            "data": {"status": "success"},
        }

        # After successful verification
        verify_url = reverse("provider-verify", kwargs={"provider": "test_provider"})
        self.client.get(verify_url, {"trx_ref": payment.transaction_ref})

        self.order.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(payment.status, "success")
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.status, "processing")

    def test_cancelled_order_payment_prevention(self):
        """Test that payments cannot be initiated for cancelled orders"""
        # Cancel the order
        self.order.status = "cancelled"
        self.order.save()

        mock_provider = Mock()
        register("test_provider", mock_provider)

        self.client.force_authenticate(user=self.user)

        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        response = self.client.post(initiate_url, {"provider": "test_provider"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancelled", response.data["error"])

        # No payment should be created
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

        # Provider should not be called
        mock_provider.initiate_payment.assert_not_called()

    def test_already_paid_order_payment_prevention(self):
        """Test that payments cannot be initiated for already paid orders"""
        # Mark order as paid
        self.order.payment_status = "paid"
        self.order.save()

        mock_provider = Mock()
        register("test_provider", mock_provider)

        self.client.force_authenticate(user=self.user)

        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )
        response = self.client.post(initiate_url, {"provider": "test_provider"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already Paid", response.data["error"])

        # Provider should not be called
        mock_provider.initiate_payment.assert_not_called()


class PaymentConcurrencyIntegrationTests(TransactionTestCase):
    """Integration tests for payment concurrency scenarios"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123",
        )

        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            status="pending",
            payment_status="unpaid",
        )

        _PROVIDERS.clear()

    def tearDown(self):
        """Clean up after each test"""
        _PROVIDERS.clear()

    @override_settings(
        PAYMENT_CALLBACK_URLS={"test_provider": "https://test-callback.com"}
    )
    def test_concurrent_payment_initiation_prevention(self):
        """Test that concurrent payment initiations are properly handled"""
        # Mock provider
        mock_provider = Mock()
        mock_provider.initiate_payment.return_value = {
            "success": True,
            "checkout_url": "https://test.com/checkout",
            "payment_id": str(uuid.uuid4()),
        }
        register("test_provider", mock_provider)

        self.client.force_authenticate(user=self.user)
        initiate_url = reverse(
            "initiate-payment", kwargs={"order_id": self.order.order_id}
        )

        # Simulate concurrent requests
        def make_payment_request():
            return self.client.post(initiate_url, {"provider": "test_provider"})

        # First request should succeed
        response1 = make_payment_request()
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request should fail (payment already in progress)
        response2 = make_payment_request()
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment in progress", response2.data["error"])

        # Should only have one payment record
        payment_count = Payment.objects.filter(order=self.order).count()
        self.assertEqual(payment_count, 1)

    def test_payment_verification_race_condition(self):
        """Test handling of concurrent payment verifications"""
        # Create payment
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="test_provider",
            amount=Decimal("100.00"),
            currency="ETB",
            transaction_ref="concurrent-tx-123",
            status="processing",
        )

        # Mock provider
        mock_provider = Mock()
        mock_provider.verify_payment.return_value = {
            "status": "success",
            "data": {"status": "success"},
        }
        register("test_provider", mock_provider)

        verify_url = reverse("provider-verify", kwargs={"provider": "test_provider"})

        # Simulate concurrent verification requests
        def verify_payment():
            return self.client.get(verify_url, {"trx_ref": payment.transaction_ref})

        response1 = verify_payment()
        response2 = verify_payment()

        # Both should succeed (idempotent operation)
        self.assertEqual(response1.status_code, 302)
        self.assertEqual(response2.status_code, 400)  # return early due to duplication

        # Payment should be in success state
        payment.refresh_from_db()
        self.assertEqual(payment.status, "success")

        # Order should be paid
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")

    def test_payment_state_consistency_under_load(self):
        """Test payment state consistency under high load scenarios"""
        # Create processing payment
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            provider="test_provider",
            amount=Decimal("100.00"),
            currency="ETB",
            transaction_ref="load-test-tx",
            status="processing",
        )

        # Mock provider with varying responses
        mock_provider = Mock()
        register("test_provider", mock_provider)

        verify_url = reverse("provider-verify", kwargs={"provider": "test_provider"})

        # Test multiple verification attempts with different outcomes
        test_scenarios = [
            {"status": "success", "data": {"status": "success"}},
            {"status": "success", "data": {"status": "success"}},  # Duplicate
            {
                "status": "failed",
                "data": {"status": "failed"},
            },  # Should not override success
        ]
        mock_provider.verify_payment.return_value = test_scenarios[0]
        response = self.client.post(
            verify_url,
            {"trx_ref": payment.transaction_ref},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)  # first successful test should pass

        for i, scenario in enumerate(
            test_scenarios[1:]
        ):  # subsquent attempt to fail after the first succeeds.
            mock_provider.verify_payment.return_value = scenario
            response = self.client.post(
                verify_url,
                {"trx_ref": payment.transaction_ref},
                content_type="application/json",
            )
            self.assertEqual(
                response.status_code, 400
            )  # last trial to override raises an error.

        # Final state should be success (first successful verification wins)
        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, "success")
        self.assertEqual(self.order.payment_status, "paid")

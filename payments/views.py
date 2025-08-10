# payments/views.py
import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, views, viewsets
from rest_framework.response import Response

from orders.models import Order

from .models import Payment
from .serializers import PaymentSerializer
from .services.registry import get_provider


class InitiatePaymentView(views.APIView):
    """
    API endpoint to start a payment process for an order.

    POST:
        - Requires authenticated user.
        - Accepts a payment provider key (e.g., 'chapa', 'paystack').
        - Creates a Payment record.
        - Calls provider's initiate_payment method.
        - Returns checkout URL for redirection (if applicable).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        """
        Initiate a payment for a specific order.

        Args:
            order_id (str): UUID or identifier of the order.

        Returns:
            Response: Checkout URL and payment ID.
        """
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        if order.payment_status not in ("unpaid", "failed"):
            return Response(
                {"error": "Order already Paid for or payment awaiting verification"},
                status=400,
            )

        if order.status == "cancelled":
            return Response(
                {
                    "error": "Sorry, but this order was cancelled. Please place another order."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider_key = request.data.get("provider", "chapa")
        currency = request.data.get("currency", "ETB")

        provider = get_provider(provider_key)
        if not provider:
            return Response({"error": "Unsupported provider"}, status=400)

        tx_ref = str(uuid.uuid4())
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                "user": request.user,
                "provider": provider_key,
                "amount": order.total_amount,
                "currency": currency,
                "transaction_ref": tx_ref,
                "status": "pending",
            },
        )

        if not created:
            # If payment exists but failed, update it for retry
            if payment.status in ["failed", "cancelled", "pending"]:
                payment.provider = provider_key
                payment.amount = order.total_amount
                payment.currency = currency
                payment.transaction_ref = str(uuid.uuid4())
                payment.status = "pending"
                payment.save()
            elif payment.status in ["processing", "success"]:
                return Response(
                    {
                        "error": "This order already has a payment in progress or completed."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        callback_base_url = settings.PAYMENT_CALLBACK_URLS.get(provider_key)

        if not callback_base_url:
            """Validate to ensure that a callback url is there, if not, exit early."""
            return Response(
                {"error": "Callback URL empty. Please update your .env file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resp = provider.initiate_payment(
            payment=payment,
            callback_url=f"{callback_base_url}/api/payments/verify/{provider_key}/",  # noqa,
        )

        if not resp["success"]:
            payment.status = "failed"
            payment.save()
            return Response(
                {"error": resp["error"]}, status=status.HTTP_400_BAD_REQUEST
            )

        payment.status = "processing"
        payment.checkout_url = resp["checkout_url"]
        payment.save()
        return Response(
            {"checkout_url": resp["checkout_url"], "payment_id": resp["payment_id"]},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ProviderVerifyView(views.APIView):
    """
    Handles both:
    - Webhook POSTs from providers
    - Redirect GETs from providers after checkout
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, provider):
        """
        Browser redirect after payment (e.g., Chapa)
        """
        trx_ref = request.GET.get("trx_ref")
        if not trx_ref:
            return Response({"error": "Missing trx_ref"}, status=400)

        return self._process_verification(provider, trx_ref, redirect_user=True)

    def post(self, request, provider):
        """
        Webhook POST from provider (e.g., PayPal IPN, Stripe webhook, etc.)
        Assumes provider sends a transaction ref in request.data
        """
        trx_ref = request.data.get("trx_ref") or request.data.get("transaction_ref")
        if not trx_ref:
            return Response({"error": "Missing trx_ref"}, status=400)

        return self._process_verification(provider, trx_ref, redirect_user=False)

    def _process_verification(self, provider, trx_ref, redirect_user=False):
        payment = Payment.objects.filter(transaction_ref=trx_ref).first()
        if not payment:
            return Response({"error": "Payment not found"}, status=404)

        if payment.status == "success":
            return Response(
                {
                    "success": False,
                    "error": "Previous payment was successful. Cannot be modified again.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        prov = get_provider(provider)
        if not prov:
            return Response({"error": "Unknown provider"}, status=400)

        verify = prov.verify_payment(transaction_ref=trx_ref)
        success = (
            verify.get("status") == "success"
            or verify.get("data", {}).get("status") == "success"
        )

        # Update DB
        payment.provider_response = verify
        payment.status = "success" if success else "failed"
        payment.save()

        order = payment.order
        order.payment_status = "paid" if success else "failed"

        if success:
            # change the order status for successful payment only.
            order.status = "processing"

        order.save()

        if redirect_user:
            # Send user to a front-end result page
            return redirect(
                f"http://localhost:3000/order-confirmed/{order.order_id}?status={'success' if success else 'failed'}"  # noqa
            )

        return Response(
            {"status": "success" if success else "failed", "details": verify}
        )


class PaymentView(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer

    def get_queryset(self):
        if getattr(
            self, "swagger_fake_view", False
        ):  # <-- swagger doc generation check
            return Payment.objects.none()
        return Payment.objects.filter(user=self.request.user).order_by("-created_at")

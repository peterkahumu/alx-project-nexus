# payments/services/chapa.py
import requests
from django.conf import settings

from .base import BasePaymentProvider
from .registry import register

CHAPA_BASE = "https://api.chapa.co/v1"


class ChapaProvider(BasePaymentProvider):
    """
    Payment provider integration for Chapa.

    Handles initiating payments, verifying transactions,
    and processing webhook callbacks for Chapa's API.
    """

    def initiate_payment(self, *, payment, callback_url=None, **kwargs):
        """
        Start a payment transaction with Chapa.

        Args:
            payment (Payment): Payment instance containing amount, currency, and user details.
            callback_url (str, optional): URL Chapa will redirect to after payment completion.
            **kwargs: Additional params (not used here).

        Returns:
            dict: JSON response from Chapa API containing transaction details.
        """
        payload = {
            "amount": str(payment.amount),
            "currency": payment.currency,
            "email": payment.user.email,
            "first_name": payment.user.first_name or "",
            "last_name": payment.user.last_name or "",
            "tx_ref": payment.transaction_ref,
            "callback_url": callback_url or settings.CHAPA_CALLBACK_URL,
        }
        headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}

        try:
            resp = requests.post(
                f"{CHAPA_BASE}/transaction/initialize",
                json=payload,
                headers=headers,
                timeout=15,
            )
            try:
                data = resp.json()
            except ValueError as e:
                return {"success": False, "error": f"Invalid JSON response: {e}"}
        except requests.RequestException as e:
            return {"success": False, "error": f"Request failed: {e}"}

        # chapa marks errors with status != "success"
        if data.get("status") != "success":
            return {
                "success": False,
                "error": data.get("message") or "Payment initialization failed.",
            }
        return {
            "success": True,
            "checkout_url": data["data"]["checkout_url"],
            "payment_id": str(payment.payment_id),
        }

    def verify_payment(self, *, transaction_ref):
        """
        Confirm payment status with Chapa.

        Args:
            transaction_ref (str): Unique transaction reference generated during initiation.

        Returns:
            dict: JSON response from Chapa verification endpoint.
        """
        headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
        r = requests.get(
            f"{CHAPA_BASE}/transaction/verify/{transaction_ref}",
            headers=headers,
            timeout=15,
        )
        return r.json()

    def handle_webhook(self, request):
        """
        Handle webhook callback from Chapa.

        Args:
            request (Request): DRF request object containing webhook payload.

        Returns:
            dict: Dictionary with transaction reference and raw payload for further processing.
        """
        data = request.data
        tx_ref = data.get("tx_ref") or data.get("txRef")
        # You can call verify_payment here for extra security if needed
        return {"transaction_ref": tx_ref, "payload": data}


# Register provider in the payment registry
register("chapa", ChapaProvider())

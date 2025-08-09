# payments/services/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from payments.models import Payment


class BasePaymentProvider(ABC):
    """Define abstract methods for the payment process"""

    @abstractmethod
    def initiate_payment(self, *, payment: "Payment", **kwargs) -> dict:
        """
        Start a payment process.

        Args:
            payment: Payment instance.
            **kwargs: Provider-specific options.

        Returns:
            dict: Must contain at least 'checkout_url' or equivalent provider-specific data.
        """

    @abstractmethod
    def verify_payment(self, *, transaction_ref: str) -> dict:
        """
        Verify payment status with the provider.

        Args:
            transaction_ref: Transaction reference from the provider.

        Returns:
            dict: Verification result.
        """

    @abstractmethod
    def handle_webhook(self, request) -> dict:
        """
        Handle provider webhook requests.

        Args:
            request: Incoming HTTP request.

        Returns:
            dict: Must include at least {'transaction_ref': str, 'payload':...}
        """

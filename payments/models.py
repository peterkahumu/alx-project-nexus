import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

from orders.models import Order

User = get_user_model()


class Payment(models.Model):
    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    PROVIDERS = [
        ("chapa", "Chapa"),
        ("paystack", "Paystack"),
        ("mpesa", "Mpesa"),
        ("cash", "Cash"),
    ]

    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="payment"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment")

    provider = models.CharField(max_length=20, choices=PROVIDERS)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    currency = models.CharField(max_length=10, default="ETB")
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default="pending")

    transaction_ref = models.CharField(
        max_length=100, unique=True
    )  # mpesa code, tx_ref(chapa), paystack_ref
    checkout_url = models.URLField(blank=True, null=True)  # online payments
    provider_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.provider.upper()} for Order # {self.order.order_number}"

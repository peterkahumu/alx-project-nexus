import uuid

from django.contrib.auth import get_user_model
from django.db import models

from products.models import Product

User = get_user_model()


# Create your models here.
class Cart(models.Model):
    """
    Represents a shopping cart linked to a specific user.
    Each user has one cart
    """

    cart_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cart_id} - {self.user.username}"


class CartItem(models.Model):
    item_id = models.UUIDField(
        primary_key=True, unique=True, default=uuid.uuid4, editable=False
    )
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [
            "cart",
            "product",
        ]  # avoid recording multiple products for a single user

    def __str__(self):
        return f"{self.quantity} X {self.product.name}"

    def get_total_price(self):
        """
        Calculates total price for this cart item
        """
        return self.quantity * self.product.unit_price

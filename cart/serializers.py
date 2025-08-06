from rest_framework import serializers

from products.models import Product

from .models import Cart, CartItem


class ProductInCartSerializer(serializers.ModelSerializer):
    """Nested product info in the cart item."""

    class Meta:
        model = Product
        fields = ["product_id", "name", "unit_price"]


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items"""

    product = ProductInCartSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True
    )

    class Meta:
        model = CartItem
        fields = ["item_id", "product", "product_id", "quantity", "get_total_price"]


class CartSerializer(serializers.ModelSerializer):
    """Serializer for the cart and all its items"""

    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ["cart_id", "user", "created_at", "items"]
        read_only_fields = ["user", "created_at"]

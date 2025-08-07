from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for individual order items."""

    class Meta:
        model = OrderItem
        fields = [
            "item_id",
            "order",
            "product",
            "product_name",
            "quantity",
            "price_per_item",
            "total_price",
            "created_at",
        ]
        read_only_fields = [
            "item_id",
            "order",
            "product_name",
            "price_per_item",
            "total_price",
            "created_at",
        ]


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for entire order including nested items."""

    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
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
        read_only_fields = [
            "order_id",
            "order_number",
            "user",
            "status",
            "payment_status",
            "subtotal",
            "tax_amount",
            "shipping_cost",
            "total_amount",
            "created_at",
            "order_items",
        ]

from django.contrib import admin

from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_id",
        "order_number",
        "user",
        "status",
        "payment_status",
        "total_amount",
        "created_at",
    ]
    list_filter = ["user", "status", "payment_status"]
    search_fields = [
        "user",
    ]
    ordering = [
        "-created_at",
    ]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "item_id",
        "order",
        "product_name",
        "quantity",
        "price_per_item",
        "total_price",
    )
    list_filter = ("created_at",)
    search_fields = ("product_name", "order__order_number")
    ordering = [
        "-created_at",
    ]

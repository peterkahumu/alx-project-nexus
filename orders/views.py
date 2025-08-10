from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cart.models import Cart, CartItem

from .models import Order, OrderItem
from .serializers import OrderSerializer


class CreateOrderFromCartView(views.APIView):
    """Creates an order from the authenticated user's cart"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        try:
            cart = Cart.objects.get(user=user)
            cart_items = CartItem.objects.filter(cart=cart)

            if not cart_items.exists():
                return Response(
                    {"error": "Your cart is empty"}, status=status.HTTP_400_BAD_REQUEST
                )

        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            subtotal = sum(
                item.product.unit_price * item.quantity for item in cart_items
            )

            tax_amount = subtotal * Decimal(
                str(settings.TAX_RATE)
            )  # configurable via settings
            shipping_cost = Decimal(
                str(settings.DEFAULT_SHIPPING_COST)
            )  # TODO: function to calculate shipping cost based on location
            total = subtotal + tax_amount + shipping_cost

            order = Order.objects.create(
                user=user,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total,
                shipping_cost=shipping_cost,
                shipping_address=request.data.get(
                    "shipping_address", request.user.address
                ),
                billing_address=request.data.get(
                    "billing_address", request.user.address
                ),
                notes=request.data.get("notes", ""),
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    price_per_item=item.product.unit_price,
                    total_price=item.product.unit_price * item.quantity,
                )

            # clear the cart
            cart_items.delete()

        serializer = OrderSerializer(order)
        return Response(
            {
                "success": "order created",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class OrderViewset(viewsets.ReadOnlyModelViewSet):
    """Handles retrieval of orders and cancelling."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(
            self, "swagger_fake_view", False
        ):  # <-- swagger doc generation check
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status != "pending":
            return Response(
                {"error": "Only pending orders can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.payment_status not in ["unpaid", "failed"]:
            return Response(
                {
                    "error": "Order already paid for. Please request for a refund instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = "cancelled"
        order.cancelled_at = timezone.now()
        order.save()

        return Response(
            {"success": "Order cancelled successfully."}, status=status.HTTP_200_OK
        )

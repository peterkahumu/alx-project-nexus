from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Cart, CartItem, Product
from .permissions import IsOwner
from .serializers import CartItemSerializer, CartSerializer


class CartViewSet(viewsets.ModelViewSet):
    """
    View for managing the user's cart.
    Only one cart per user.
    """

    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(
            self, "swagger_fake_view", False
        ):  # <-- swagger doc generation check
            return Cart.objects.none()
        return Cart.objects.filter(user=self.request.user)

    def get_object(self):
        """Always return the current user's cart"""
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def list(self, request, *args, **kwargs):
        """Redirect list to detail view 1-1 relationship"""
        cart = self.get_object()
        return Response(self.get_serializer(cart).data)

    def create(self, request, *args, **kwargs):
        """Override create to handle existing cart"""
        cart, created = Cart.objects.get_or_create(user=request.user)
        if created:
            serializer = self.get_serializer(cart)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        serializer = self.get_serializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemViewSet(viewsets.ModelViewSet):
    """
    View for managing cart items:
    add/update/remove
    """

    serializer_class = CartItemSerializer
    permission_classes = [IsOwner]

    def get_queryset(self):
        if getattr(
            self, "swagger_fake_view", False
        ):  # <-- swagger doc generation check
            return CartItem.objects.none()
        return CartItem.objects.filter(cart__user=self.request.user)

    def create(self, request, *args, **kwargs):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))

        if quantity < 1:
            return Response(
                {"error": "Invalid quantity"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = get_object_or_404(Product, pk=product_id)

        existing_item = CartItem.objects.filter(cart=cart, product=product).first()

        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            serializer = self.get_serializer(existing_item)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(cart=cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

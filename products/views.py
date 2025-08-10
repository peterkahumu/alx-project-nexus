from django.db.models import Q
from rest_framework import viewsets

from .models import Category, Product
from .permissions import IsAdminOrReadOnly
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD API for product categories.

    - List, retrieve, create, update, and delete categories.
    - Only admin users can modify; others have read-only access.
    - Automatically sets `created_by` to the request user on creation.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD API for products.

    - List, retrieve, create, update, and delete products.
    - Only admin users can modify; others have read-only access.
    - Automatically sets `created_by` to the request user on creation.
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        """Apply filters if any are provided."""
        queryset = Product.objects.all()
        category = self.request.GET.get("category")
        featured = self.request.GET.get("featured")

        if category:
            queryset = queryset.filter(
                Q(category__category_id__iexact=category)
                | Q(category__name__iexact=category)
            )
        if featured:
            queryset = queryset.filter(featured=True)

        return queryset

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet

# Initialize router
router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)

# URLs
urlpatterns = [
    path("", include(router.urls)),
]

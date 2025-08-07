from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CreateOrderFromCartView, OrderViewset

router = DefaultRouter()
router.register(r"", OrderViewset, basename="orders")


urlpatterns = [
    path("create-order/", CreateOrderFromCartView.as_view(), name="create-order"),
    path("", include(router.urls)),
]

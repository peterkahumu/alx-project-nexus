from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Allows access only to the object owner
    """

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "cart"):
            return obj.cart.user == request.user
        return False

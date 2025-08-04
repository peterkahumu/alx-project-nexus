import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import AllUserManager, UserManager


class User(AbstractUser):
    """
    Custom User model with:
    - UUID primary key
    - Soft delete functionality (via `deleted_at`)
    - Extended fields: phone, role, profile image
    """

    user_id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, primary_key=True
    )
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("customer", "Customer"),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="customer",
    )

    profile_image = models.ImageField(
        upload_to="profile_pictures", null=True, blank=True
    )

    address = models.JSONField(null=True, blank=True)

    # Soft delete + timestamp tracking
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Attach custom managers
    objects = UserManager()  # filters out soft-deleted users
    all_objects = AllUserManager()  # includes soft-deleted users

    # Use username for login; email is required field
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    def __str__(self):
        """Return string representation of the user"""
        return self.username

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete the user by setting deleted_at timestamp.
        """
        self.deleted_at = timezone.now()
        self.save()
        return (0, {})

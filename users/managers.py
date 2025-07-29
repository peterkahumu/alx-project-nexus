from django.contrib.auth.models import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom user manager that:
    - Filters out soft-deleted users (deleted_at is null)
    - Validates required fields
    - Automatically sets role to 'admin' for superusers
    """

    def get_queryset(self):
        # Return only non-deleted users
        return super().get_queryset().filter(deleted_at__isnull=True)

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Create a regular user with strict email validation.
        """
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """
        Create a superuser with admin role and elevated privileges.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(username, email, password, **extra_fields)


class AllUserManager(models.Manager):
    """
    Returns all users regardless of soft-deleted status.
    Useful for admin/audit purposes.
    """

    def get_queryset(self):
        return super().get_queryset()

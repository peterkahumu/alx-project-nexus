from django.contrib import admin

from .models import Category, Product


# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_by", "is_active"]
    search_fields = ["name", "description", "created_by"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "description",
        "created_by",
        "unit_price",
        "original_price",
        "in_stock",
    ]
    search_fields = ["name", "description", "created_by", "category"]

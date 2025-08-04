from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = [
            "category_id",
            "slug",
            "created_by",
            "created_at",
            "updated_at",
        ]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = [
            "product_id",
            "slug",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        user = self.context["request"].user
        name = attrs.get("name")

        if self.instance:
            # On update, exclude current instance from the check
            if (
                Product.objects.filter(created_by=user, name=name)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise serializers.ValidationError(
                    {"name": "You already have a product with this name."}
                )
        else:
            if Product.objects.filter(created_by=user, name=name).exists():
                raise serializers.ValidationError(
                    {"name": "You already have a product with this name."}
                )

        return attrs

from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    """Returns the payments made by the user."""

    class Meta:
        model = Payment
        fields = [
            "payment_id",
            "amount",
            "currency",
            "status",
            "transaction_ref",
            "created_at",
        ]
        read_only_fields = fields

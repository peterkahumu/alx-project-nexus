from django.contrib import admin

from .models import Payment


# Register your models here.
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Define the appearance and action in the admin panel
    """

    list_display = [
        "payment_id",
        "order__order_number",
        "user",
        "provider",
        "transaction_ref",
        "currency",
        "amount",
        "status",
    ]
    list_filter = ["user", "provider", "currency", "status"]

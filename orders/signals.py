"""
Send an email to the user when any of the following happens:
1. New order is placed.
2. The order status changes
3. If payment status changes
4. If payment fails (even if previous state was payment failed.)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order
from .tasks import send_order_email


@receiver(post_save, sender=Order)
def send_order_created_email(sender, instance, created, **kwargs):

    user_fullname = str(instance.user.first_name) + " " + str(instance.user.last_name)

    if created:
        send_order_email.delay(
            event="created",
            order_id=str(instance.order_id),
            user_email=instance.user.email,
            user_fullname=user_fullname,
        )


@receiver(pre_save, sender=Order)
def send_order_update_emails(sender, instance, **kwargs):
    user_fullname = str(instance.user.first_name) + " " + str(instance.user.last_name)

    try:
        old = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if old.status != instance.status:
        send_order_email.delay(
            event="status_changed",
            order_id=str(instance.order_id),
            user_fullname=user_fullname,
            user_email=instance.user.email,
            old_value=old.status,
            new_value=instance.status,
        )

    if old.payment_status != instance.payment_status:
        send_order_email.delay(
            event="payment_status_changed",
            order_id=str(instance.order_id),
            user_email=instance.user.email,
            old_value=old.payment_status,
            new_value=instance.payment_status,
            user_fullname=user_fullname,
        )

    # If payment failed
    if instance.payment_status == "failed" and old.payment_status != "failed":
        send_order_email.delay(
            event="payment_failed",
            order_id=str(instance.order_id),
            user_email=instance.user.email,
            user_fullname=user_fullname,
        )

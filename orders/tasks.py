"""Send emails to the user based on Order events"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)


@shared_task
def send_order_email(
    event, order_id, user_fullname, user_email, old_value=None, new_value=None
):
    try:
        order = Order.objects.get(order_id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_id} does not exist")
        return

    subject = "Order update"
    message = f"Hello {user_fullname}.\n\n "

    if event == "created":
        subject = "🎉 Order placed successfully."
        message += (
            f"Thank you for placing order #{order.order_number}. "
            "We will update you once shipping starts"
        )

    elif event == "status_changed":
        subject = "📦 Order Status Updated"
        message += f"Order #{order.order_number} status changed from '{old_value}' to '{new_value}'."  # noqa

    elif event == "payment_status_changed":
        subject = "💳 Payment Status Updated"
        message += f"Order #{order.order_number} payment status changed from '{old_value}' to '{new_value}'."  # noqa

    elif event == "payment_failed":
        now = timezone.now().strftime("%d %b %Y, %I:%M %p")
        subject = "🚫 Payment Failed"
        message += (
            f"Payment for Order #{order.order_number} failed.\n"
            f"Amount: {order.total_amount}\n"
            f"Time: {now}\n"
            f"Please try again."
        )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )

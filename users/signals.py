from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User
from .tasks import send_activation_email


@receiver(post_save, sender=User)
def send_activation_email_signal(sender, instance, created, **kwargs):
    if created and not instance.is_active:  # Only send email for inactive users
        # Generate secure token using user ID (not email)
        uid = urlsafe_base64_encode(force_bytes(instance.pk))
        token = default_token_generator.make_token(instance)
        confirm_url = (
            f"{settings.FRONTEND_URL}/api/users/confirm-email/?uid={uid}&token={token}"
        )

        try:
            send_activation_email.delay(instance.email, confirm_url)

        except Exception:
            import traceback

            traceback.print_exc()
    return

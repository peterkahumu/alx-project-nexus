from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_activation_email(email, confirmation_url):
    subject = "Confirm your email"
    message = f"""
    Welcome! Thank you for registering.\n

    Please click the link below to activate your account:\n
    {confirmation_url}\n

    This link will expire in 24 hours for security reasons.\n

    If you didn't create this account, please ignore this email.\n

    Best regards,
    The Team
    """
    send_mail(
        subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

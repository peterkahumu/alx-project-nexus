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


@shared_task
def send_password_reset_email(email, reset_url, first_name=""):
    """Send password reset email"""
    greeting = f"Hi {first_name}, " if first_name else "Hi"

    subject = "Reset your password"
    message = f"""
    {greeting}

    You requested to reset your password. Click the link below to set a new password:
    {reset_url}

    This link will expire in 24 hours for security reasons.

    You can ignore the email if you did not request a password reset.

    For security reasons, this link can only be used once.

    Best regards,
    The Team
    """

    send_mail(
        subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False
    )

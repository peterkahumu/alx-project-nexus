from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_activation_email(email, confirmation_url):
    print(f"Sending to {email} with link {confirmation_url}")
    subject = "Confirm your email"
    message = f"Click the link to activate your account: {confirmation_url}"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

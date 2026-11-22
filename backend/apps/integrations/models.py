from django.conf import settings
from django.db import models

from .fields import EncryptedTextField


class Connection(models.Model):
    """A user's connected third-party account and the OAuth tokens that reach it."""

    class Provider(models.TextChoices):
        GOOGLE_CALENDAR = "google_calendar", "Google Calendar"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="integration_connections"
    )
    provider = models.CharField(max_length=32, choices=Provider.choices)
    account_email = models.EmailField()
    refresh_token = EncryptedTextField()
    access_token = EncryptedTextField()
    access_token_expires_at = models.DateTimeField()
    scopes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "provider"], name="integrations_one_connection_per_provider")
        ]

    def __str__(self):
        return f"{self.get_provider_display()} for {self.user}"

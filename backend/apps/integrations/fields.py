from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def fernet() -> Fernet:
    """The cipher for stored tokens. Read at use time, so a server without the key still starts."""
    key = settings.INTEGRATIONS_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("Set INTEGRATIONS_ENCRYPTION_KEY to store integration tokens.")
    try:
        return Fernet(key)
    except ValueError as error:
        raise ImproperlyConfigured("INTEGRATIONS_ENCRYPTION_KEY is not a valid Fernet key.") from error


class EncryptedTextField(models.TextField):
    """Text that Python code reads in plain form and the database stores encrypted with Fernet."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return None if value is None else fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        try:
            return fernet().decrypt(value.encode()).decode()
        except InvalidToken as error:
            raise ImproperlyConfigured(
                "A stored integration token does not decrypt with INTEGRATIONS_ENCRYPTION_KEY."
            ) from error

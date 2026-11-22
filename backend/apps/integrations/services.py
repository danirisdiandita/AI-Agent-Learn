"""Write operations for integrations: connect an account through OAuth, and disconnect it."""

from enum import StrEnum

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

from . import google
from .catalog import Integration
from .fields import fernet
from .models import Connection

# The user has this long to finish Google's consent screen.
STATE_MAX_AGE_SECONDS = 600


class NotConfigured(Exception):
    """The server has no OAuth client for this integration."""


class Failure(StrEnum):
    """Why a connection did not complete. The callback sends the dashboard one of these codes."""

    DENIED = "denied"
    EXPIRED = "expired"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class ConnectFailed(Exception):
    def __init__(self, failure: Failure):
        super().__init__(failure)
        self.failure = failure


def _state_salt(integration: Integration) -> str:
    # One salt per integration, so a state issued for one integration never completes another.
    return f"integrations.{integration.id}.state"


def start_connection(*, user, integration: Integration) -> str:
    """Returns the provider URL where the user grants access. Its state names the user for the callback."""
    client = integration.oauth_client()
    if client is None:
        raise NotConfigured(
            f"{integration.name} is not configured on this server. "
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
        )
    # Fail now, not after the user grants access, if the server cannot store the tokens.
    fernet()
    state = signing.dumps(user.pk, salt=_state_salt(integration))
    return client.authorization_url(state=state)


def finish_connection(*, integration: Integration, state: str, code: str, error: str) -> Connection:
    """Completes the provider's redirect. Raises ConnectFailed with the reason the dashboard shows."""
    if error:
        raise ConnectFailed(Failure.DENIED)
    try:
        user_id = signing.loads(state, salt=_state_salt(integration), max_age=STATE_MAX_AGE_SECONDS)
        user = get_user_model().objects.get(pk=user_id)
    except (signing.BadSignature, get_user_model().DoesNotExist):
        raise ConnectFailed(Failure.EXPIRED) from None
    client = integration.oauth_client()
    if client is None:
        raise ConnectFailed(Failure.NOT_CONFIGURED)
    try:
        tokens = client.exchange(code=code)
    except google.GoogleError as exc:
        raise ConnectFailed(Failure.FAILED) from exc
    return _save_connection(user=user, integration=integration, tokens=tokens)


def _save_connection(*, user, integration: Integration, tokens: google.Tokens) -> Connection:
    # Connecting again updates the one row per user and provider. Google omits the refresh token when it
    # reuses an earlier grant, and the stored one stays valid then.
    with transaction.atomic():
        connection = (
            Connection.objects.select_for_update()
            .filter(user=user, provider=integration.provider)
            .first()
        ) or Connection(user=user, provider=integration.provider)
        refresh_token = tokens.refresh_token or connection.refresh_token
        if not refresh_token:
            raise ConnectFailed(Failure.FAILED)
        connection.refresh_token = refresh_token
        connection.account_email = tokens.email
        connection.access_token = tokens.access_token
        connection.access_token_expires_at = tokens.expires_at
        connection.scopes = tokens.scopes
        connection.save()
    return connection


def disconnect(*, user, integration: Integration) -> None:
    """Revokes the grant at the provider when it can, and forgets the tokens. Safe to call twice."""
    connection = Connection.objects.filter(user=user, provider=integration.provider).first()
    if connection is None:
        return
    try:
        google.revoke(connection.refresh_token)
    except google.GoogleError:
        # The user may have revoked access in their Google account already. The row goes either way.
        pass
    connection.delete()

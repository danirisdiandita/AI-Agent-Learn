"""Write operations for integrations: connect an account through OAuth, disconnect it, and act on it."""

import logging
from datetime import timedelta
from enum import StrEnum

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.utils import timezone

from . import google
from .catalog import INTEGRATIONS, Integration
from .fields import fernet
from .models import Connection

# The user has this long to finish Google's consent screen.
STATE_MAX_AGE_SECONDS = 600
# Refresh an access token this long before it expires, so it cannot expire on the way to Google.
REFRESH_MARGIN = timedelta(minutes=1)
GOOGLE_CALENDAR = INTEGRATIONS["google-calendar"]

logger = logging.getLogger(__name__)


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


class CalendarError(Exception):
    """Google Calendar did not create the event. The message says why, for the user and the model."""


def create_calendar_event(*, user, summary, start, end, time_zone, description=None) -> dict:
    """Creates an event in the primary calendar of the user's connected Google account.

    `start` and `end` are ISO 8601 local date-times in the IANA zone `time_zone`. Returns the event's id, its
    `html_link` in Google Calendar, its summary, and its start and end. Raises CalendarError.
    """
    connection = Connection.objects.filter(user=user, provider=GOOGLE_CALENDAR.provider).first()
    if connection is None:
        raise CalendarError("Google Calendar is not connected. Connect it on the Integrations screen.")
    event = {
        "summary": summary,
        "start": {"dateTime": start, "timeZone": time_zone},
        "end": {"dateTime": end, "timeZone": time_zone},
    }
    if description:
        event["description"] = description
    try:
        created = google.create_event(access_token=_access_token(connection), event=event)
    except google.GoogleError as error:
        logger.warning("Google Calendar did not create an event: %s", error)
        if error.status in (401, 403):
            raise CalendarError(
                "Google refused access to the calendar. Connect Google Calendar again on the Integrations screen."
            ) from error
        raise CalendarError("Google Calendar did not create the event. Try again later.") from error
    return {
        "id": created.get("id"),
        "html_link": created.get("htmlLink"),
        "summary": created.get("summary", summary),
        "start": start,
        "end": end,
    }


def _access_token(connection: Connection) -> str:
    """The connection's access token, refreshed through Google first when it is about to expire."""
    if connection.access_token_expires_at > timezone.now() + REFRESH_MARGIN:
        return connection.access_token
    client = GOOGLE_CALENDAR.oauth_client()
    if client is None:
        raise CalendarError("Google Calendar is not configured on this server.")
    try:
        fresh = client.refresh(refresh_token=connection.refresh_token)
    except google.GoogleError as error:
        logger.warning("Google did not refresh an access token: %s", error)
        raise CalendarError(
            "Google no longer accepts the saved access. Connect Google Calendar again on the Integrations screen."
        ) from error
    connection.access_token = fresh.token
    connection.access_token_expires_at = fresh.expires_at
    connection.save(update_fields=["access_token", "access_token_expires_at", "updated_at"])
    return fresh.token

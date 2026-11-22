"""The integrations this server offers. URLs and the list endpoint come from this table."""

from dataclasses import dataclass

from django.conf import settings

from . import google
from .models import Connection


@dataclass(frozen=True)
class Integration:
    id: str
    name: str
    description: str
    provider: Connection.Provider
    scopes: tuple[str, ...]

    def oauth_client(self) -> google.Client | None:
        """The OAuth client from settings, or None while the server has no client ID and secret."""
        if not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
            return None
        return google.Client(
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
            scopes=self.scopes,
        )


INTEGRATIONS = {
    integration.id: integration
    for integration in [
        Integration(
            id="google-calendar",
            name="Google Calendar",
            description="Read and manage the calendars and events of a Google account.",
            provider=Connection.Provider.GOOGLE_CALENDAR,
            scopes=("openid", "email", "https://www.googleapis.com/auth/calendar"),
        ),
    ]
}

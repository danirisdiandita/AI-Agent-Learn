"""Google's OAuth 2.0 endpoints for web server apps, over the standard library. No Django here."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
TIMEOUT_SECONDS = 10


class GoogleError(Exception):
    """Google refused the request or sent a response this client cannot read."""


@dataclass(frozen=True)
class Tokens:
    access_token: str
    # Google sends a refresh token only when the user grants consent, so a repeat sign-in may omit it.
    refresh_token: str | None
    expires_at: datetime
    scopes: str
    email: str


@dataclass(frozen=True)
class Client:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...]

    def authorization_url(self, *, state: str) -> str:
        # Offline access with forced consent makes Google return a refresh token every time.
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def exchange(self, *, code: str) -> Tokens:
        body = _post(
            TOKEN_URL,
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        try:
            # The ID token came straight from Google's token endpoint over TLS, so its signature needs no check.
            claims = jwt.decode(body["id_token"], options={"verify_signature": False})
            return Tokens(
                access_token=body["access_token"],
                refresh_token=body.get("refresh_token"),
                expires_at=datetime.now(UTC) + timedelta(seconds=int(body["expires_in"])),
                scopes=body.get("scope", " ".join(self.scopes)),
                email=claims["email"],
            )
        except (KeyError, TypeError, ValueError, jwt.InvalidTokenError) as error:
            raise GoogleError(f"Unexpected token response: {error!r}") from error


def revoke(token: str) -> None:
    """Revokes a token and every grant made with it. Raises GoogleError when Google does not confirm."""
    _post(REVOKE_URL, {"token": token})


def _post(url: str, form: dict[str, str]) -> dict:
    request = Request(
        url,
        data=urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except (URLError, TimeoutError) as error:
        # HTTPError is a URLError, so a 4xx or 5xx from Google lands here too.
        raise GoogleError(f"{url} failed: {error}") from error
    try:
        return json.loads(raw) if raw else {}
    except ValueError as error:
        raise GoogleError(f"{url} sent a body that is not JSON") from error

"""A stand-in for Google's OAuth and Calendar endpoints, so no test reaches the network.

Patch it over the client's urlopen: mock.patch("apps.integrations.google.urlopen", FakeGoogle().urlopen).
"""

import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qsl

import jwt

TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def token_response(*, access="access-1", refresh="refresh-1", email="ada@gmail.com"):
    body = {
        "access_token": access,
        "expires_in": 3599,
        "scope": "openid email https://www.googleapis.com/auth/calendar",
        "token_type": "Bearer",
        "id_token": jwt.encode({"email": email, "sub": "123"}, "any-key-the-client-never-checks-it", algorithm="HS256"),
    }
    if refresh:
        body["refresh_token"] = refresh
    return body


def event_response(**fields):
    return {
        "id": "evt123",
        "htmlLink": "https://www.google.com/calendar/event?eid=evt123",
        "summary": "Design review",
        "status": "confirmed",
        **fields,
    }


class FakeGoogle:
    """Answers in place of Google and records every request. Set `failing[url]` to an HTTP status to refuse a URL."""

    def __init__(self):
        self.requests = []
        self.headers = []
        self.responses = {TOKEN_URL: token_response(), REVOKE_URL: {}, EVENTS_URL: event_response()}
        self.failing = {}

    def urlopen(self, request, timeout):
        body = request.data.decode()
        is_json = request.get_header("Content-type") == "application/json"
        self.requests.append((request.full_url, json.loads(body) if is_json else dict(parse_qsl(body))))
        self.headers.append(dict(request.header_items()))
        if request.full_url in self.failing:
            status = self.failing[request.full_url]
            raise HTTPError(request.full_url, status, "Refused", {}, io.BytesIO(b'{"error": "invalid_grant"}'))
        return io.BytesIO(json.dumps(self.responses[request.full_url]).encode())

    def sent_to(self, url):
        return [body for sent_url, body in self.requests if sent_url == url]

    def authorization_sent_to(self, url):
        return [h.get("Authorization") for (sent_url, _), h in zip(self.requests, self.headers) if sent_url == url]

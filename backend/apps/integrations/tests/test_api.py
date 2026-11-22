import io
import json
import time
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, parse_qsl, urlsplit

import jwt
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.db import connection as db
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User

from ..models import Connection

LIST_URL = "/api/v1/integrations/"
CONNECT_URL = "/api/v1/integrations/google-calendar/connect/"
CALLBACK_URL = "/api/v1/integrations/google-calendar/callback/"
DISCONNECT_URL = "/api/v1/integrations/google-calendar/"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REDIRECT_URI = "http://localhost:5174/api/v1/integrations/google-calendar/callback/"


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


class FakeGoogle:
    """Answers in place of Google's OAuth endpoints and records every request, so no test reaches the network."""

    def __init__(self):
        self.requests = []
        self.responses = {TOKEN_URL: token_response(), REVOKE_URL: {}}
        self.failing = set()

    def urlopen(self, request, timeout):
        self.requests.append((request.full_url, dict(parse_qsl(request.data.decode()))))
        if request.full_url in self.failing:
            raise HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error": "invalid_grant"}'))
        return io.BytesIO(json.dumps(self.responses[request.full_url]).encode())

    def sent_to(self, url):
        return [form for sent_url, form in self.requests if sent_url == url]


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="client-123.apps.googleusercontent.com",
    GOOGLE_OAUTH_CLIENT_SECRET="secret-456",
    GOOGLE_OAUTH_REDIRECT_URI=REDIRECT_URI,
    INTEGRATIONS_ENCRYPTION_KEY=Fernet.generate_key().decode(),
)
class IntegrationsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada@example.com", "correct-horse-battery")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        # Google redirects a browser to the callback, which carries no bearer token.
        self.browser = APIClient()
        self.google = FakeGoogle()
        patcher = mock.patch("apps.integrations.google.urlopen", self.google.urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self):
        """Starts a connection and returns the query Google receives the user with."""
        response = self.client.post(CONNECT_URL)
        self.assertEqual(response.status_code, 200)
        url = urlsplit(response.data["authorization_url"])
        return {key: values[0] for key, values in parse_qs(url.query).items()}

    def finish(self, **query):
        return self.browser.get(CALLBACK_URL, query)

    def connect(self):
        response = self.finish(state=self.start()["state"], code="code-1")
        self.assertEqual(response["Location"], "/integrations?connected=google-calendar")

    def test_list_shows_each_integration_and_whether_it_is_connected(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item["id"], "google-calendar")
        self.assertEqual(item["name"], "Google Calendar")
        self.assertTrue(item["description"])
        self.assertIs(item["configured"], True)
        self.assertIsNone(item["connection"])

    def test_list_requires_sign_in(self):
        self.assertEqual(APIClient().get(LIST_URL).status_code, 401)

    def test_connect_returns_google_consent_url(self):
        response = self.client.post(CONNECT_URL)
        url = urlsplit(response.data["authorization_url"])
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://accounts.google.com/o/oauth2/v2/auth")
        self.assertEqual(query["client_id"], "client-123.apps.googleusercontent.com")
        self.assertEqual(query["redirect_uri"], REDIRECT_URI)
        self.assertEqual(query["response_type"], "code")
        self.assertEqual(query["scope"].split(), ["openid", "email", "https://www.googleapis.com/auth/calendar"])
        self.assertEqual(query["access_type"], "offline")
        self.assertEqual(query["prompt"], "consent")
        self.assertTrue(query["state"])
        self.assertEqual(self.google.requests, [])

    def test_callback_stores_the_connection_with_encrypted_tokens(self):
        self.connect()

        self.assertEqual(
            self.google.sent_to(TOKEN_URL),
            [
                {
                    "code": "code-1",
                    "client_id": "client-123.apps.googleusercontent.com",
                    "client_secret": "secret-456",
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                }
            ],
        )
        stored = Connection.objects.get(user=self.user)
        self.assertEqual(stored.account_email, "ada@gmail.com")
        self.assertEqual(stored.access_token, "access-1")
        self.assertEqual(stored.refresh_token, "refresh-1")
        with db.cursor() as cursor:
            cursor.execute("SELECT access_token, refresh_token FROM integrations_connection")
            raw_access, raw_refresh = cursor.fetchone()
        self.assertNotIn("access-1", raw_access)
        self.assertNotIn("refresh-1", raw_refresh)

        item = self.client.get(LIST_URL).data[0]
        self.assertEqual(item["connection"]["account_email"], "ada@gmail.com")
        self.assertTrue(item["connection"]["connected_at"])

    def test_callback_with_a_forged_state_connects_nothing(self):
        response = self.finish(state="forged", code="code-1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/integrations?error=expired")
        self.assertEqual(self.google.requests, [])
        self.assertFalse(Connection.objects.exists())

    def test_callback_after_ten_minutes_connects_nothing(self):
        state = self.start()["state"]
        with mock.patch("time.time", return_value=time.time() + 601):
            response = self.finish(state=state, code="code-1")
        self.assertEqual(response["Location"], "/integrations?error=expired")
        self.assertFalse(Connection.objects.exists())

    def test_callback_when_the_user_declines(self):
        response = self.finish(state=self.start()["state"], error="access_denied")
        self.assertEqual(response["Location"], "/integrations?error=denied")
        self.assertEqual(self.google.requests, [])
        self.assertFalse(Connection.objects.exists())

    def test_callback_when_google_rejects_the_code(self):
        self.google.failing.add(TOKEN_URL)
        response = self.finish(state=self.start()["state"], code="code-1")
        self.assertEqual(response["Location"], "/integrations?error=failed")
        self.assertFalse(Connection.objects.exists())

    def test_reconnecting_updates_the_row_and_keeps_the_refresh_token(self):
        self.connect()
        self.google.responses[TOKEN_URL] = token_response(access="access-2", refresh=None)
        self.connect()

        stored = Connection.objects.get(user=self.user)
        self.assertEqual(stored.access_token, "access-2")
        self.assertEqual(stored.refresh_token, "refresh-1")

    def test_a_first_connection_without_a_refresh_token_fails(self):
        self.google.responses[TOKEN_URL] = token_response(refresh=None)
        response = self.finish(state=self.start()["state"], code="code-1")
        self.assertEqual(response["Location"], "/integrations?error=failed")
        self.assertFalse(Connection.objects.exists())

    def test_disconnect_revokes_the_grant_and_forgets_the_tokens(self):
        self.connect()
        response = self.client.delete(DISCONNECT_URL)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.google.sent_to(REVOKE_URL), [{"token": "refresh-1"}])
        self.assertFalse(Connection.objects.exists())
        self.assertIsNone(self.client.get(LIST_URL).data[0]["connection"])
        self.assertEqual(self.client.delete(DISCONNECT_URL).status_code, 204)

    def test_disconnect_forgets_the_tokens_when_google_refuses_the_revoke(self):
        self.connect()
        self.google.failing.add(REVOKE_URL)
        self.assertEqual(self.client.delete(DISCONNECT_URL).status_code, 204)
        self.assertFalse(Connection.objects.exists())

    def test_users_see_only_their_own_connection(self):
        self.connect()
        other = User.objects.create_user("grace@example.com", "correct-horse-battery")
        self.client.force_authenticate(other)
        self.assertIsNone(self.client.get(LIST_URL).data[0]["connection"])

    def test_unknown_integration_is_not_found(self):
        self.assertEqual(self.client.post("/api/v1/integrations/nope/connect/").status_code, 404)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET="")
    def test_without_a_client_the_integration_is_not_configured(self):
        self.assertIs(self.client.get(LIST_URL).data[0]["configured"], False)
        response = self.client.post(CONNECT_URL)
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_OAUTH_CLIENT_ID", response.data["detail"])

    @override_settings(INTEGRATIONS_ENCRYPTION_KEY="")
    def test_connect_without_an_encryption_key_fails_before_google(self):
        with self.assertRaises(ImproperlyConfigured):
            self.client.post(CONNECT_URL)

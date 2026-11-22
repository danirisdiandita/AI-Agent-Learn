from datetime import timedelta
from unittest import mock

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User

from .. import selectors, services
from ..models import Connection
from .fake_google import EVENTS_URL, TOKEN_URL, FakeGoogle, token_response


def connect(user, *, expires_in=timedelta(minutes=30), access="access-1"):
    return Connection.objects.create(
        user=user,
        provider=Connection.Provider.GOOGLE_CALENDAR,
        account_email="ada@gmail.com",
        refresh_token="refresh-1",
        access_token=access,
        access_token_expires_at=timezone.now() + expires_in,
        scopes="openid email https://www.googleapis.com/auth/calendar",
    )


EVENT = {
    "summary": "Design review",
    "start": "2026-11-23T15:00:00",
    "end": "2026-11-23T15:30:00",
    "time_zone": "Asia/Jakarta",
}


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="client-123.apps.googleusercontent.com",
    GOOGLE_OAUTH_CLIENT_SECRET="secret-456",
    INTEGRATIONS_ENCRYPTION_KEY=Fernet.generate_key().decode(),
)
class CreateCalendarEventTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada@example.com", "pw-unused-123")
        self.google = FakeGoogle()
        patcher = mock.patch("apps.integrations.google.urlopen", self.google.urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, **fields):
        return services.create_calendar_event(user=self.user, **{**EVENT, **fields})

    def test_google_receives_the_event_in_its_time_zone_with_the_stored_token(self):
        connect(self.user)
        created = self.create(description="Bring the mockups")
        self.assertEqual(
            self.google.sent_to(EVENTS_URL),
            [
                {
                    "summary": "Design review",
                    "start": {"dateTime": "2026-11-23T15:00:00", "timeZone": "Asia/Jakarta"},
                    "end": {"dateTime": "2026-11-23T15:30:00", "timeZone": "Asia/Jakarta"},
                    "description": "Bring the mockups",
                }
            ],
        )
        self.assertEqual(self.google.authorization_sent_to(EVENTS_URL), ["Bearer access-1"])
        self.assertEqual(self.google.sent_to(TOKEN_URL), [])
        self.assertEqual(
            created,
            {
                "id": "evt123",
                "html_link": "https://www.google.com/calendar/event?eid=evt123",
                "summary": "Design review",
                "start": "2026-11-23T15:00:00",
                "end": "2026-11-23T15:30:00",
            },
        )

    def test_an_event_without_a_description_sends_none(self):
        connect(self.user)
        self.create()
        self.assertNotIn("description", self.google.sent_to(EVENTS_URL)[0])

    def test_an_expired_token_is_refreshed_and_saved_first(self):
        connect(self.user, expires_in=timedelta(minutes=-5))
        self.google.responses[TOKEN_URL] = token_response(access="access-2", refresh=None)
        self.create()
        self.assertEqual(
            self.google.sent_to(TOKEN_URL),
            [
                {
                    "refresh_token": "refresh-1",
                    "client_id": "client-123.apps.googleusercontent.com",
                    "client_secret": "secret-456",
                    "grant_type": "refresh_token",
                }
            ],
        )
        self.assertEqual(self.google.authorization_sent_to(EVENTS_URL), ["Bearer access-2"])
        stored = Connection.objects.get(user=self.user)
        self.assertEqual((stored.access_token, stored.refresh_token), ("access-2", "refresh-1"))
        self.assertGreater(stored.access_token_expires_at, timezone.now() + timedelta(minutes=50))

    def test_a_token_that_expires_within_a_minute_is_refreshed(self):
        connect(self.user, expires_in=timedelta(seconds=30))
        self.create()
        self.assertEqual(len(self.google.sent_to(TOKEN_URL)), 1)

    def test_a_refused_refresh_creates_nothing_and_says_to_connect_again(self):
        connect(self.user, expires_in=timedelta(minutes=-5))
        self.google.failing[TOKEN_URL] = 400
        with self.assertLogs("apps.integrations.services"), self.assertRaisesRegex(services.CalendarError, "Connect Google Calendar again"):
            self.create()
        self.assertEqual(self.google.sent_to(EVENTS_URL), [])

    def test_without_a_connection_nothing_reaches_google(self):
        with self.assertRaisesRegex(services.CalendarError, "not connected"):
            self.create()
        self.assertEqual(self.google.requests, [])

    def test_a_refused_insert_is_a_calendar_error(self):
        connect(self.user)
        for status, says in ((401, "Connect Google Calendar again"), (500, "did not create the event")):
            with self.subTest(status=status):
                self.google.failing[EVENTS_URL] = status
                with self.assertLogs("apps.integrations.services"), self.assertRaisesRegex(services.CalendarError, says):
                    self.create()


class HasConnectionTests(TestCase):
    @override_settings(INTEGRATIONS_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_only_the_users_own_connection_counts(self):
        ada = User.objects.create_user("ada@example.com", "pw-unused-123")
        grace = User.objects.create_user("grace@example.com", "pw-unused-123")
        connect(grace)
        provider = Connection.Provider.GOOGLE_CALENDAR
        self.assertFalse(selectors.has_connection(user=ada, provider=provider))
        self.assertTrue(selectors.has_connection(user=grace, provider=provider))

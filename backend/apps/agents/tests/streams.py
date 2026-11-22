"""Helpers for tests of the chat endpoints, which answer with server-sent events."""

import json
from unittest import mock

from django.test import TestCase
from engine.testing import FakeClient
from rest_framework.test import APIClient

from apps.accounts.models import User

SESSIONS_URL = "/api/v1/agents/sessions/"


def session_url(session_id):
    return f"{SESSIONS_URL}{session_id}/"


def messages_url(session_id):
    return f"{SESSIONS_URL}{session_id}/messages/"


def reply_url(session_id):
    return f"{SESSIONS_URL}{session_id}/reply/"


def decision_url(call_id):
    return f"/api/v1/agents/tool-calls/{call_id}/decision/"


def read_events(response):
    """The (name, data) of each server-sent event in a streamed response."""
    body = b"".join(response.streaming_content).decode()
    events = []
    for block in body.split("\n\n"):
        if not block:
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def names(events):
    return [name for name, _ in events]


def data(events, name):
    """The data of every event with this name."""
    return [payload for event, payload in events if event == name]


class ChatTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada@example.com", "pw-unused-123")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_session(self, client=None):
        response = (client or self.client).post(SESSIONS_URL)
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def stream(self, url, body, *steps):
        """Posts to a streaming endpoint with a fake model that plays `steps`. Returns the response, its events (None
        for a plain JSON answer), and the fake model."""
        model = FakeClient(*steps)
        with mock.patch("apps.agents.runtime.model_client", return_value=model):
            response = self.client.post(url, body, format="json")
            events = read_events(response) if response.get("Content-Type") == "text/event-stream" else None
        return response, events, model

    def send(self, session_id, content, *steps, time_zone="UTC"):
        return self.stream(messages_url(session_id), {"content": content, "time_zone": time_zone}, *steps)

    def decide(self, call_id, approve, *steps, time_zone="UTC"):
        return self.stream(decision_url(call_id), {"approve": approve, "time_zone": time_zone}, *steps)

    def messages(self, session_id):
        return self.client.get(session_url(session_id)).data["messages"]

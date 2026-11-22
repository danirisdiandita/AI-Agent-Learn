import json
import os
import urllib.error
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User

CHAT_URL = "/api/v1/agents/chat/"
MESSAGES = [{"role": "user", "content": "Hello"}]


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self, *args):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ChatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("ada@example.com", "pw-unused-123"))

    def test_requires_sign_in(self):
        response = APIClient().post(CHAT_URL, {"messages": MESSAGES}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_rejects_empty_conversation(self):
        response = self.client.post(CHAT_URL, {"messages": []}, format="json")
        self.assertEqual(response.status_code, 400)

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_without_api_key_says_how_to_set_it(self):
        response = self.client.post(CHAT_URL, {"messages": MESSAGES}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENROUTER_API_KEY", response.data["detail"])

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"})
    def test_returns_the_model_reply(self):
        reply = {"choices": [{"message": {"role": "assistant", "content": "Hi there"}}]}
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(reply)) as urlopen:
            response = self.client.post(CHAT_URL, {"messages": MESSAGES}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"message": {"role": "assistant", "content": "Hi there"}})
        sent = urlopen.call_args.args[0]
        self.assertEqual(sent.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(sent.data), {"model": "test/model", "messages": MESSAGES})

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_unreachable_openrouter_logs_the_reason(self):
        failure = urllib.error.URLError("certificate verify failed")
        with mock.patch("urllib.request.urlopen", side_effect=failure), self.assertLogs("apps.agents.services") as logs:
            response = self.client.post(CHAT_URL, {"messages": MESSAGES}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("certificate verify failed", logs.output[0])

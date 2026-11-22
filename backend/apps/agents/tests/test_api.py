import io
import json
import os
import urllib.error
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.agents.models import ChatMessage

SESSIONS_URL = "/api/v1/agents/sessions/"


def session_url(session_id):
    return f"{SESSIONS_URL}{session_id}/"


def messages_url(session_id):
    return f"{SESSIONS_URL}{session_id}/messages/"


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self, *args):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def reply(content, model=None):
    body = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    return FakeResponse({**body, "model": model} if model else body)


def sent_messages(urlopen, call=-1):
    """The conversation that a faked urlopen call sent to OpenRouter."""
    return json.loads(urlopen.call_args_list[call].args[0].data)["messages"]


@mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/requested"})
class ChatSessionApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada@example.com", "pw-unused-123")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_session(self, client=None):
        response = (client or self.client).post(SESSIONS_URL)
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def send(self, session_id, content, answer="Hi there", model="vendor/model-a"):
        with mock.patch("urllib.request.urlopen", return_value=reply(answer, model)) as urlopen:
            response = self.client.post(messages_url(session_id), {"content": content}, format="json")
        return response, urlopen

    def test_requires_sign_in(self):
        session_id = self.create_session()
        anonymous = APIClient()
        self.assertEqual(anonymous.get(SESSIONS_URL).status_code, 401)
        self.assertEqual(anonymous.post(SESSIONS_URL).status_code, 401)
        self.assertEqual(anonymous.get(session_url(session_id)).status_code, 401)
        self.assertEqual(anonymous.post(messages_url(session_id), {"content": "Hi"}, format="json").status_code, 401)
        self.assertEqual(anonymous.delete(session_url(session_id)).status_code, 401)

    def test_create_returns_an_empty_session(self):
        response = self.client.post(SESSIONS_URL)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), {"id", "title", "created_at", "updated_at", "messages"})
        self.assertIsNone(response.data["title"])
        self.assertEqual(response.data["messages"], [])

    def test_send_saves_the_message_and_the_reply(self):
        session_id = self.create_session()
        response, _ = self.send(session_id, "Hello", answer="Hi there", model="vendor/model-a")
        self.assertEqual(response.status_code, 201)
        saved = [(m["role"], m["content"], m["model"]) for m in response.data["messages"]]
        self.assertEqual(saved, [("user", "Hello", None), ("assistant", "Hi there", "vendor/model-a")])

        detail = self.client.get(session_url(session_id)).data
        self.assertEqual(detail["messages"], response.data["messages"])
        self.assertEqual(detail["title"], "Hello")

    def test_send_gives_the_model_the_whole_history(self):
        session_id = self.create_session()
        self.send(session_id, "Hello", answer="Hi there")
        _, urlopen = self.send(session_id, "What is a tool call?")
        self.assertEqual(
            sent_messages(urlopen),
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "What is a tool call?"},
            ],
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(request.data)["model"], "test/requested")

    def test_reply_without_a_model_records_the_requested_model(self):
        session_id = self.create_session()
        response, _ = self.send(session_id, "Hello", model=None)
        self.assertEqual(response.data["messages"][1]["model"], "test/requested")

    def test_detail_lists_messages_in_the_order_they_were_sent(self):
        session_id = self.create_session()
        self.send(session_id, "First", answer="Reply one")
        self.send(session_id, "Second", answer="Reply two")
        detail = self.client.get(session_url(session_id)).data
        self.assertEqual(
            [(m["role"], m["content"]) for m in detail["messages"]],
            [("user", "First"), ("assistant", "Reply one"), ("user", "Second"), ("assistant", "Reply two")],
        )
        self.assertEqual(set(detail["messages"][0]), {"id", "role", "content", "model", "created_at"})

    def test_list_puts_the_latest_activity_first_with_a_title_from_the_first_message(self):
        older = self.create_session()
        newer = self.create_session()
        self.send(newer, "x" * 200)
        empty = self.create_session()
        self.send(older, "Plan a trip")
        self.send(older, "Add a day in Lisbon")

        sessions = self.client.get(SESSIONS_URL).data
        self.assertEqual([s["id"] for s in sessions], [older, empty, newer])
        titles = {s["id"]: s["title"] for s in sessions}
        self.assertEqual(titles[older], "Plan a trip")
        self.assertEqual(titles[newer], "x" * 80)
        self.assertIsNone(titles[empty])
        self.assertEqual(set(sessions[0]), {"id", "title", "created_at", "updated_at"})

    def test_list_shows_only_the_users_sessions(self):
        mine = self.create_session()
        other = APIClient()
        other.force_authenticate(User.objects.create_user("grace@example.com", "pw-unused-123"))
        self.create_session(other)
        self.assertEqual([s["id"] for s in self.client.get(SESSIONS_URL).data], [mine])

    def test_another_users_session_is_not_found(self):
        session_id = self.create_session()
        self.send(session_id, "Hello")
        intruder = APIClient()
        intruder.force_authenticate(User.objects.create_user("grace@example.com", "pw-unused-123"))
        with mock.patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(intruder.get(session_url(session_id)).status_code, 404)
            response = intruder.post(messages_url(session_id), {"content": "Hi"}, format="json")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(intruder.delete(session_url(session_id)).status_code, 404)
        urlopen.assert_not_called()
        self.assertEqual(len(self.client.get(session_url(session_id)).data["messages"]), 2)

    def test_unknown_session_is_not_found(self):
        self.assertEqual(self.client.get(session_url(999999)).status_code, 404)
        self.assertEqual(self.client.delete(session_url(999999)).status_code, 404)

    def test_delete_removes_the_session_and_its_messages(self):
        session_id = self.create_session()
        self.send(session_id, "Hello")
        self.assertEqual(self.client.delete(session_url(session_id)).status_code, 204)
        self.assertEqual(self.client.get(session_url(session_id)).status_code, 404)
        self.assertEqual(self.client.get(SESSIONS_URL).data, [])
        self.assertFalse(ChatMessage.objects.filter(session_id=session_id).exists())

    def test_blank_content_is_rejected(self):
        session_id = self.create_session()
        with mock.patch("urllib.request.urlopen") as urlopen:
            for body in ({"content": "   "}, {"content": ""}, {}):
                response = self.client.post(messages_url(session_id), body, format="json")
                self.assertEqual(response.status_code, 400, body)
        urlopen.assert_not_called()
        self.assertEqual(self.client.get(session_url(session_id)).data["messages"], [])

    def assert_nothing_saved(self, session_id, before):
        after = self.client.get(session_url(session_id)).data
        self.assertEqual(after["messages"], before["messages"])
        self.assertEqual(after["updated_at"], before["updated_at"])

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_without_an_api_key_nothing_is_saved(self):
        session_id = self.create_session()
        before = self.client.get(session_url(session_id)).data
        response = self.client.post(messages_url(session_id), {"content": "Hello"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENROUTER_API_KEY", response.data["detail"])
        self.assert_nothing_saved(session_id, before)

    def test_upstream_error_saves_nothing(self):
        session_id = self.create_session()
        before = self.client.get(session_url(session_id)).data
        refused = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b"rate limited"))
        with mock.patch("urllib.request.urlopen", side_effect=refused), self.assertLogs("apps.agents.openrouter"):
            response = self.client.post(messages_url(session_id), {"content": "Hello"}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assert_nothing_saved(session_id, before)

    def test_unreachable_openrouter_logs_the_reason_and_saves_nothing(self):
        session_id = self.create_session()
        before = self.client.get(session_url(session_id)).data
        failure = urllib.error.URLError("certificate verify failed")
        with mock.patch("urllib.request.urlopen", side_effect=failure), self.assertLogs("apps.agents.openrouter") as logs:
            response = self.client.post(messages_url(session_id), {"content": "Hello"}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("certificate verify failed", logs.output[0])
        self.assert_nothing_saved(session_id, before)

    def test_session_deleted_while_the_model_answers_saves_nothing(self):
        session_id = self.create_session()

        def delete_then_reply(*args, **kwargs):
            self.client.delete(session_url(session_id))
            return reply("Too late")

        with mock.patch("urllib.request.urlopen", side_effect=delete_then_reply):
            response = self.client.post(messages_url(session_id), {"content": "Hello"}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ChatMessage.objects.filter(session_id=session_id).exists())

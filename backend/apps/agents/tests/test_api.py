import io
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from django.test import override_settings
from engine.testing import reply
from engine.types import AssistantMessage, ModelError, SystemMessage, TextDelta, UserMessage
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.agents.models import ChatMessage

from .streams import (
    SESSIONS_URL,
    ChatTestCase,
    data,
    messages_url,
    names,
    read_events,
    reply_url,
    session_url,
)

RECORDED_TEXT_STREAM = Path(__file__).resolve().parents[3] / "engine" / "tests" / "fixtures" / "text.sse"


@mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/requested"})
class ChatSessionApiTests(ChatTestCase):
    def test_requires_sign_in(self):
        session_id = self.create_session()
        anonymous = APIClient()
        self.assertEqual(anonymous.get(SESSIONS_URL).status_code, 401)
        self.assertEqual(anonymous.post(SESSIONS_URL).status_code, 401)
        self.assertEqual(anonymous.get(session_url(session_id)).status_code, 401)
        self.assertEqual(anonymous.post(messages_url(session_id), {"content": "Hi"}, format="json").status_code, 401)
        self.assertEqual(anonymous.post(reply_url(session_id), {}, format="json").status_code, 401)
        self.assertEqual(anonymous.delete(session_url(session_id)).status_code, 401)

    def test_create_returns_an_empty_session(self):
        response = self.client.post(SESSIONS_URL)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), {"id", "title", "created_at", "updated_at", "messages"})
        self.assertIsNone(response.data["title"])
        self.assertEqual(response.data["messages"], [])

    def test_send_streams_the_reply_and_saves_both_messages(self):
        session_id = self.create_session()
        response, events, _ = self.send(session_id, "Hello", reply("Hi there", model="vendor/model-a"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertEqual(names(events), ["user_message", "delta", "delta", "assistant_message", "done"])
        self.assertEqual("".join(d["text"] for d in data(events, "delta")), "Hi there")

        saved = self.messages(session_id)
        self.assertEqual(
            [(m["role"], m["content"], m["model"]) for m in saved],
            [("user", "Hello", None), ("assistant", "Hi there", "vendor/model-a")],
        )
        self.assertEqual(data(events, "user_message"), [saved[0]])
        self.assertEqual(data(events, "assistant_message"), [saved[1]])
        self.assertEqual(self.client.get(session_url(session_id)).data["title"], "Hello")

    def test_the_model_reads_the_system_prompt_and_the_whole_history(self):
        session_id = self.create_session()
        self.send(session_id, "Hello", reply("Hi there"))
        _, _, model = self.send(session_id, "What is a tool call?", reply("A step."))
        messages = model.sent[0][0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertEqual(
            messages[1:],
            [UserMessage("Hello"), AssistantMessage("Hi there"), UserMessage("What is a tool call?")],
        )

    def test_the_system_prompt_gives_the_time_in_the_users_time_zone(self):
        session_id = self.create_session()
        now = datetime(2026, 11, 22, 6, 5, tzinfo=UTC)
        with mock.patch("django.utils.timezone.now", return_value=now):
            _, _, model = self.send(session_id, "Hello", reply("Hi"), time_zone="Asia/Jakarta")
        prompt = model.sent[0][0][0].content
        self.assertIn("It is Sunday 2026-11-22 13:05 in the user's time zone, Asia/Jakarta.", prompt)
        self.assertIn("2026-11-22T06:05Z", prompt)

    def test_an_unknown_time_zone_falls_back_to_utc(self):
        session_id = self.create_session()
        for time_zone in ("Mars/Olympus_Mons", "../../etc/passwd", ""):
            with self.subTest(time_zone=time_zone):
                _, _, model = self.send(session_id, "Hello", reply("Hi"), time_zone=time_zone)
                self.assertIn("in the user's time zone, UTC.", model.sent[0][0][0].content)

    def test_the_configured_openrouter_model_streams_through(self):
        session_id = self.create_session()
        stream = io.BytesIO(RECORDED_TEXT_STREAM.read_bytes())
        with mock.patch("urllib.request.urlopen", return_value=stream) as urlopen:
            events = read_events(self.client.post(messages_url(session_id), {"content": "Hello"}, format="json"))
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertIn(b'"model": "test/requested"', request.data)
        self.assertGreater(len(data(events, "delta")), 1)
        self.assertEqual(data(events, "assistant_message")[0]["content"], "Hello! Nice to meet you today.")

    def test_detail_lists_messages_in_the_order_they_were_sent(self):
        session_id = self.create_session()
        self.send(session_id, "First", reply("Reply one"))
        self.send(session_id, "Second", reply("Reply two"))
        detail = self.messages(session_id)
        self.assertEqual(
            [(m["role"], m["content"]) for m in detail],
            [("user", "First"), ("assistant", "Reply one"), ("user", "Second"), ("assistant", "Reply two")],
        )
        self.assertEqual(set(detail[0]), {"id", "role", "content", "model", "created_at", "tool_calls"})

    def test_list_puts_the_latest_activity_first_with_a_title_from_the_first_message(self):
        older = self.create_session()
        newer = self.create_session()
        self.send(newer, "x" * 200, reply("Hi"))
        empty = self.create_session()
        self.send(older, "Plan a trip", reply("Where to?"))
        self.send(older, "Add a day in Lisbon", reply("Done."))

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
        self.send(session_id, "Hello", reply("Hi"))
        self.client.force_authenticate(User.objects.create_user("grace@example.com", "pw-unused-123"))
        self.assertEqual(self.client.get(session_url(session_id)).status_code, 404)
        response, _, model = self.send(session_id, "Hi")
        self.assertEqual(response.status_code, 404)
        response, _, _ = self.stream(reply_url(session_id), {})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(session_url(session_id)).status_code, 404)
        self.assertEqual(ChatMessage.objects.filter(session_id=session_id).count(), 2)

    def test_unknown_session_is_not_found(self):
        self.assertEqual(self.client.get(session_url(999999)).status_code, 404)
        self.assertEqual(self.client.delete(session_url(999999)).status_code, 404)

    def test_delete_removes_the_session_and_its_messages(self):
        session_id = self.create_session()
        self.send(session_id, "Hello", reply("Hi"))
        self.assertEqual(self.client.delete(session_url(session_id)).status_code, 204)
        self.assertEqual(self.client.get(session_url(session_id)).status_code, 404)
        self.assertEqual(self.client.get(SESSIONS_URL).data, [])
        self.assertFalse(ChatMessage.objects.filter(session_id=session_id).exists())

    def test_blank_content_is_rejected_before_the_model_is_called(self):
        session_id = self.create_session()
        for body in ({"content": "   "}, {"content": ""}, {}):
            with self.subTest(body=body):
                response, _, model = self.stream(messages_url(session_id), body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(model.sent, [])
        self.assertEqual(self.messages(session_id), [])

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_without_an_api_key_nothing_is_saved(self):
        session_id = self.create_session()
        before = self.client.get(session_url(session_id)).data
        response = self.client.post(messages_url(session_id), {"content": "Hello"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENROUTER_API_KEY", response.data["detail"])
        after = self.client.get(session_url(session_id)).data
        self.assertEqual((after["messages"], after["updated_at"]), ([], before["updated_at"]))

    def test_a_reply_that_fails_midway_keeps_the_users_message(self):
        session_id = self.create_session()
        _, events, _ = self.send(session_id, "Hello", [TextDelta("Hel"), ModelError("Cannot reach OpenRouter.")])
        self.assertEqual(names(events), ["user_message", "delta", "error", "done"])
        self.assertEqual(data(events, "error"), [{"detail": "Cannot reach OpenRouter.", "status": 502}])
        self.assertEqual([(m["role"], m["content"]) for m in self.messages(session_id)], [("user", "Hello")])

    def test_reply_answers_the_message_whose_reply_failed(self):
        session_id = self.create_session()
        self.send(session_id, "Hello", [ModelError("Cannot reach OpenRouter.")])
        response, events, model = self.stream(reply_url(session_id), {"time_zone": "UTC"}, reply("Hi again"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(names(events), ["delta", "delta", "assistant_message", "done"])
        self.assertEqual(model.sent[0][0][1:], [UserMessage("Hello")])
        self.assertEqual(
            [(m["role"], m["content"]) for m in self.messages(session_id)], [("user", "Hello"), ("assistant", "Hi again")]
        )

    def test_reply_refuses_when_there_is_nothing_to_answer(self):
        session_id = self.create_session()
        response, _, _ = self.stream(reply_url(session_id), {})
        self.assertEqual(response.status_code, 409)
        self.send(session_id, "Hello", reply("Hi"))
        response, _, model = self.stream(reply_url(session_id), {})
        self.assertEqual(response.status_code, 409)
        self.assertIn("answered already", response.data["detail"])
        self.assertEqual(model.sent, [])

    def test_session_deleted_while_the_model_answers_saves_nothing_more(self):
        session_id = self.create_session()

        def delete_then_answer():
            self.client.delete(session_url(session_id))
            yield TextDelta("Too late")

        def stream(**kwargs):
            yield from delete_then_answer()
            yield from reply("Too late")[-1:]

        with mock.patch("engine.testing.FakeClient.stream", side_effect=stream):
            _, events, _ = self.send(session_id, "Hello")
        self.assertEqual(data(events, "error"), [{"detail": "This chat was deleted.", "status": 404}])
        self.assertFalse(ChatMessage.objects.filter(session_id=session_id).exists())


@mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "AGENTS_SCRIPTED_MODEL": "1"})
class ScriptedModelTests(ChatTestCase):
    """scripts/e2e-dashboard.sh runs the chat with a scripted model, which a production server must never use."""

    def post(self):
        return self.client.post(messages_url(self.create_session()), {"content": "Hello"}, format="json")

    def test_a_server_without_debug_ignores_the_flag(self):
        self.assertEqual(self.post().status_code, 503)

    @override_settings(DEBUG=True)
    def test_a_debug_server_with_the_flag_streams_the_scripted_reply(self):
        events = read_events(self.post())
        self.assertEqual(data(events, "assistant_message")[0]["model"], "e2e/scripted-model")
        self.assertGreater(len(data(events, "delta")), 1)

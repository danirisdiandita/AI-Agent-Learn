import os
from datetime import timedelta
from unittest import mock

from cryptography.fernet import Fernet
from django.test import override_settings
from django.utils import timezone
from engine.testing import calls, reply
from engine.types import AssistantMessage, ToolCall, ToolMessage
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.agents.models import ChatToolCall
from apps.integrations.models import Connection
from apps.integrations.tests.fake_google import EVENTS_URL, TOKEN_URL, FakeGoogle, token_response

from .streams import ChatTestCase, data, decision_url, names, reply_url

ASKED = {"summary": "Design review", "start": "2026-11-23T15:00:00", "end": "2026-11-23T15:30:00"}
# What the card shows and Google receives: the model's arguments, with the user's time zone filled in.
PREPARED = {**ASKED, "time_zone": "Asia/Jakarta"}
CREATED = {
    "id": "evt123",
    "html_link": "https://www.google.com/calendar/event?eid=evt123",
    "summary": "Design review",
    "start": "2026-11-23T15:00:00",
    "end": "2026-11-23T15:30:00",
}


def schedule(call_id="call-1", **arguments):
    return calls(ToolCall(call_id, "create_calendar_event", {**ASKED, **arguments}))


@mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="client-123.apps.googleusercontent.com",
    GOOGLE_OAUTH_CLIENT_SECRET="secret-456",
    INTEGRATIONS_ENCRYPTION_KEY=Fernet.generate_key().decode(),
)
class CalendarToolTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.google = FakeGoogle()
        patcher = mock.patch("apps.integrations.google.urlopen", self.google.urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.session_id = self.create_session()

    def connect(self, user=None, expires_in=timedelta(minutes=30)):
        return Connection.objects.create(
            user=user or self.user,
            provider=Connection.Provider.GOOGLE_CALENDAR,
            account_email="ada@gmail.com",
            refresh_token="refresh-1",
            access_token="access-1",
            access_token_expires_at=timezone.now() + expires_in,
            scopes="openid email https://www.googleapis.com/auth/calendar",
        )

    def ask(self, *steps):
        """Sends a scheduling request that the model answers with `steps`. Returns the stream's events."""
        _, events, _ = self.send(self.session_id, "Schedule a design review", *steps, time_zone="Asia/Jakarta")
        return events

    def pending_call(self):
        self.connect()
        return data(self.ask(schedule()), "tool_call")[0]["id"]

    def test_the_tool_is_offered_only_with_a_connected_calendar(self):
        _, _, model = self.send(self.session_id, "Schedule a design review", reply("Connect it first."))
        messages, tools = model.sent[0]
        self.assertEqual(tools, [])
        self.assertIn("connect Google Calendar on the Integrations screen", messages[0].content)

        self.connect()
        _, _, model = self.send(self.session_id, "Try again", reply("Which day?"))
        messages, tools = model.sent[0]
        self.assertEqual([tool.name for tool in tools], ["create_calendar_event"])
        self.assertEqual(tools[0].parameters["required"], ["summary", "start", "end"])
        self.assertIn("create_calendar_event", messages[0].content)

    def test_another_users_connection_does_not_offer_the_tool(self):
        self.connect(user=User.objects.create_user("grace@example.com", "pw-unused-123"))
        _, _, model = self.send(self.session_id, "Schedule a design review", reply("Connect it first."))
        self.assertEqual(model.sent[0][1], [])

    def test_a_requested_event_waits_for_approval_and_nothing_reaches_google(self):
        self.connect()
        events = self.ask(schedule())
        self.assertEqual(names(events), ["user_message", "tool_call", "assistant_message", "done"])
        call = data(events, "tool_call")[0]
        self.assertEqual(
            {key: call[key] for key in ("name", "arguments", "status", "result", "decided_at")},
            {"name": "create_calendar_event", "arguments": PREPARED, "status": "pending", "result": None, "decided_at": None},
        )
        reply_message = data(events, "assistant_message")[0]
        self.assertEqual((reply_message["content"], reply_message["tool_calls"]), ("", [call]))
        self.assertEqual(self.messages(self.session_id)[1], reply_message)
        self.assertEqual(self.google.requests, [])

    def test_a_new_message_waits_until_the_call_is_decided(self):
        self.pending_call()
        response, _, model = self.send(self.session_id, "Never mind")
        self.assertEqual(response.status_code, 409)
        response, _, _ = self.stream(reply_url(self.session_id), {})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(model.sent, [])
        self.assertEqual(len(self.messages(self.session_id)), 2)

    def test_approving_creates_the_event_and_the_model_reads_the_result(self):
        call_id = self.pending_call()
        response, events, model = self.decide(call_id, True, reply("It is on your calendar."))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.google.sent_to(EVENTS_URL),
            [
                {
                    "summary": "Design review",
                    "start": {"dateTime": "2026-11-23T15:00:00", "timeZone": "Asia/Jakarta"},
                    "end": {"dateTime": "2026-11-23T15:30:00", "timeZone": "Asia/Jakarta"},
                }
            ],
        )
        self.assertEqual(names(events), ["tool_call", "delta", "delta", "delta", "delta", "delta", "assistant_message", "done"])
        decided = data(events, "tool_call")[0]
        self.assertEqual((decided["status"], decided["result"]), ("succeeded", CREATED))
        self.assertIsNotNone(decided["decided_at"])
        history = model.sent[0][0]
        self.assertEqual(
            history[-2:],
            [AssistantMessage("", (ToolCall("call-1", "create_calendar_event", PREPARED),)), ToolMessage("call-1", CREATED)],
        )
        self.assertEqual(self.messages(self.session_id)[1]["tool_calls"], [decided])

    def test_declining_creates_nothing_and_tells_the_model(self):
        call_id = self.pending_call()
        _, events, model = self.decide(call_id, False, reply("Okay, I did not add it."))
        self.assertEqual(self.google.requests, [])
        decided = data(events, "tool_call")[0]
        self.assertEqual((decided["status"], decided["result"]), ("declined", {"declined": True}))
        self.assertEqual(model.sent[0][0][-1], ToolMessage("call-1", {"declined": True}))
        self.assertEqual(data(events, "assistant_message")[0]["content"], "Okay, I did not add it.")
        # The chat takes new messages again.
        response, _, _ = self.send(self.session_id, "Thanks", reply("You are welcome."))
        self.assertEqual(response.status_code, 200)

    def test_a_second_decision_on_the_same_call_is_refused(self):
        call_id = self.pending_call()
        self.decide(call_id, True, reply("Done."))
        for approve in (True, False):
            response, _, model = self.decide(call_id, approve)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(model.sent, [])
        self.assertEqual(len(self.google.sent_to(EVENTS_URL)), 1)
        self.assertEqual(ChatToolCall.objects.get(pk=call_id).status, "succeeded")

    def test_another_users_call_is_not_found(self):
        call_id = self.pending_call()
        self.client.force_authenticate(User.objects.create_user("grace@example.com", "pw-unused-123"))
        for target in (call_id, 999999):
            response, _, _ = self.decide(target, True)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(ChatToolCall.objects.get(pk=call_id).status, "pending")
        self.assertEqual(self.google.requests, [])

    def test_a_decision_needs_sign_in_and_a_yes_or_no(self):
        call_id = self.pending_call()
        self.assertEqual(APIClient().post(decision_url(call_id), {"approve": True}, format="json").status_code, 401)
        response, _, _ = self.stream(decision_url(call_id), {})
        self.assertEqual(response.status_code, 400)

    def test_without_a_model_the_call_stays_pending(self):
        call_id = self.pending_call()
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            response = self.client.post(decision_url(call_id), {"approve": True}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(ChatToolCall.objects.get(pk=call_id).status, "pending")
        self.assertEqual(self.google.requests, [])

    def test_an_expired_token_is_refreshed_before_the_event_is_created(self):
        self.connect(expires_in=timedelta(minutes=-1))
        call_id = data(self.ask(schedule()), "tool_call")[0]["id"]
        self.google.responses[TOKEN_URL] = token_response(access="access-2", refresh=None)
        self.decide(call_id, True, reply("Done."))
        self.assertEqual(self.google.sent_to(TOKEN_URL)[0]["grant_type"], "refresh_token")
        self.assertEqual(self.google.authorization_sent_to(EVENTS_URL), ["Bearer access-2"])

    def test_a_calendar_disconnected_before_approval_fails_without_calling_google(self):
        call_id = self.pending_call()
        Connection.objects.filter(user=self.user).delete()
        _, events, model = self.decide(call_id, True, reply("Connect Google Calendar again."))
        decided = data(events, "tool_call")[0]
        self.assertEqual(decided["status"], "failed")
        self.assertIn("no longer connected", decided["result"]["error"])
        self.assertEqual(self.google.requests, [])
        self.assertEqual(model.sent[0][0][-1], ToolMessage("call-1", decided["result"]))

    def test_an_event_google_refuses_is_failed_and_the_model_hears_why(self):
        call_id = self.pending_call()
        self.google.failing[EVENTS_URL] = 500
        with self.assertLogs("apps.integrations.services"):
            _, events, model = self.decide(call_id, True, reply("Google refused it."))
        decided = data(events, "tool_call")[0]
        self.assertEqual((decided["status"], decided["result"]), ("failed", {"error": "Google Calendar did not create the event. Try again later."}))
        self.assertEqual(data(events, "assistant_message")[0]["content"], "Google refused it.")

    def test_unusable_arguments_go_back_to_the_model_instead_of_the_user(self):
        self.connect()
        events = self.ask(schedule(summary=""), reply("What should I call the event?"))
        failed = data(events, "tool_call")[0]
        self.assertEqual((failed["status"], failed["result"]), ("failed", {"error": "Give the event a summary, such as its title."}))
        self.assertEqual(data(events, "assistant_message")[-1]["content"], "What should I call the event?")
        self.assertFalse(ChatToolCall.objects.filter(status="pending").exists())

    def test_an_event_that_ends_before_it_starts_is_sent_back(self):
        self.connect()
        events = self.ask(schedule(end="2026-11-23T14:00:00"), reply("When should it end?"))
        self.assertEqual(data(events, "tool_call")[0]["result"], {"error": "The event must end after it starts."})

    def test_an_offset_becomes_the_wall_clock_of_the_events_zone(self):
        self.connect()
        events = self.ask(schedule(start="2026-11-23T08:00:00Z", end="2026-11-23T08:30:00+00:00", time_zone="Asia/Jakarta"))
        arguments = data(events, "tool_call")[0]["arguments"]
        self.assertEqual((arguments["start"], arguments["end"]), ("2026-11-23T15:00:00", "2026-11-23T15:30:00"))

    def test_the_model_answers_once_every_call_of_a_step_is_decided(self):
        self.connect()
        both = calls(
            ToolCall("call-1", "create_calendar_event", ASKED),
            ToolCall("call-2", "create_calendar_event", {**ASKED, "summary": "Retro"}),
        )
        first, second = (call["id"] for call in data(self.ask(both), "tool_call"))
        _, events, model = self.decide(first, False)
        self.assertEqual(names(events), ["tool_call", "done"])
        self.assertEqual(model.sent, [])
        _, events, model = self.decide(second, True, reply("Added the retro."))
        self.assertEqual(names(events)[-2:], ["assistant_message", "done"])
        created = data(events, "tool_call")[0]["result"]
        self.assertEqual(model.sent[0][0][-2:], [ToolMessage("call-1", {"declined": True}), ToolMessage("call-2", created)])

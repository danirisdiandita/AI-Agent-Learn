from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from django.utils import timezone

from apps.agents.models import ChatMessage, ChatSession, ChatToolCall


class ChatMessageConstraintTests(TestCase):
    def setUp(self):
        self.session = ChatSession.objects.create(user=User.objects.create_user("ada@example.com", "pw-unused-123"))

    def assert_rejected(self, **fields):
        with self.assertRaises(IntegrityError):
            ChatMessage.objects.create(session=self.session, content="Hello", **fields)

    def test_unknown_role_is_rejected(self):
        self.assert_rejected(role="system")

    def test_user_message_with_a_model_is_rejected(self):
        self.assert_rejected(role="user", model="vendor/model")

    def test_assistant_message_without_a_model_is_rejected(self):
        self.assert_rejected(role="assistant", model=None)

    def test_valid_messages_are_saved(self):
        ChatMessage.objects.create(session=self.session, role="user", content="Hello")
        ChatMessage.objects.create(session=self.session, role="assistant", content="Hi", model="vendor/model")
        self.assertEqual(list(self.session.messages.values_list("role", flat=True)), ["user", "assistant"])

    def test_a_reply_that_only_calls_tools_may_have_no_text(self):
        ChatMessage.objects.create(session=self.session, role="assistant", content="", model="vendor/model")


class ChatToolCallConstraintTests(TestCase):
    def setUp(self):
        session = ChatSession.objects.create(user=User.objects.create_user("ada@example.com", "pw-unused-123"))
        self.message = ChatMessage.objects.create(session=session, role="assistant", content="", model="vendor/model")

    def create(self, **fields):
        return ChatToolCall.objects.create(
            message=self.message, name="create_calendar_event", arguments={"summary": "Standup"}, **fields
        )

    def assert_rejected(self, **fields):
        # A savepoint per attempt, so one rejected insert does not end the test's transaction.
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create(**{"call_id": "call-x", **fields})

    def test_unknown_status_is_rejected(self):
        self.assert_rejected(status="maybe")

    def test_a_pending_or_running_call_has_no_result_yet(self):
        self.assert_rejected(status="pending", result={"declined": True})
        self.assert_rejected(status="approved", decided_at=timezone.now(), result={"id": "evt"})

    def test_a_settled_call_has_a_result(self):
        for status in ("declined", "succeeded", "failed"):
            with self.subTest(status=status):
                self.assert_rejected(status=status, decided_at=timezone.now())

    def test_a_pending_call_has_no_decision_time(self):
        self.assert_rejected(status="pending", decided_at=timezone.now())

    def test_a_call_id_appears_once_per_message(self):
        self.create(call_id="call-1")
        self.assert_rejected(call_id="call-1")

    def test_valid_calls_are_saved(self):
        self.create(call_id="call-1")
        self.create(call_id="call-2", status="declined", decided_at=timezone.now(), result={"declined": True})
        self.create(call_id="call-3", status="failed", result={"error": "Name the room."})
        self.assertEqual(list(self.message.tool_calls.values_list("status", flat=True)), ["pending", "declined", "failed"])

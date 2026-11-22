from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.agents.models import ChatMessage, ChatSession


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

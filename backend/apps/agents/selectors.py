"""Read queries for agents.

Each selector is a function that returns a queryset or plain values. Put select_related and
prefetch_related here, so views never build queries themselves.
"""

from django.db.models import OuterRef, Subquery
from django.db.models.functions import Left

from .models import ChatMessage, ChatRole, ChatSession

TITLE_LENGTH = 80


def chat_sessions(*, user):
    """The user's chat sessions, the most recently active first.

    Each has a `title`: the start of its first user message, or None before the first message.
    """
    first_user_message = ChatMessage.objects.filter(session=OuterRef("pk"), role=ChatRole.USER).order_by("id")
    title = Subquery(first_user_message.values(start=Left("content", TITLE_LENGTH))[:1])
    return ChatSession.objects.filter(user=user).annotate(title=title).order_by("-updated_at", "-id")


def chat_session(*, user, session_id):
    """One of the user's chat sessions with its title, its messages, and their tool calls, or None when the user has no
    such session."""
    return chat_sessions(user=user).prefetch_related("messages__tool_calls").filter(pk=session_id).first()

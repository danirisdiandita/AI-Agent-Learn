"""Write operations for agents: create, update, and delete, with their business rules.

Each service is a function with keyword-only arguments. It validates, writes, and returns model instances.
Wrap multi-step writes in transaction.atomic(). The api layer and other apps call these; they never write models directly.
"""

from django.db import transaction
from django.utils import timezone

from . import openrouter
from .models import ChatMessage, ChatRole, ChatSession


def create_chat_session(*, user):
    return ChatSession.objects.create(user=user)


def delete_chat_session(*, user, session_id):
    """Deletes one of the user's sessions with its messages. Returns False when the user has no such session."""
    deleted, _ = ChatSession.objects.filter(user=user, pk=session_id).delete()
    return deleted > 0


def send_chat_message(*, session, content):
    """Sends the session's messages and `content` to the model, then saves `content` and the reply.

    Returns the saved user message and assistant message. Raises openrouter.ChatError when the model call fails, and
    then saves nothing. The model call runs outside any transaction, so it holds no database lock while it waits.
    """
    history = [{"role": message.role, "content": message.content} for message in session.messages.all()]
    reply = openrouter.complete(messages=[*history, {"role": ChatRole.USER, "content": content}])
    with transaction.atomic():
        # Updating the session first locks its row, so two sends to one session save their pairs one after the other.
        if not ChatSession.objects.filter(pk=session.pk).update(updated_at=timezone.now()):
            raise openrouter.ChatError("This chat was deleted.", status=404)
        return [
            ChatMessage.objects.create(session=session, role=ChatRole.USER, content=content),
            ChatMessage.objects.create(session=session, role=ChatRole.ASSISTANT, content=reply.content, model=reply.model),
        ]

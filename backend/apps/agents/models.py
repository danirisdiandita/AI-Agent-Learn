from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    """One conversation in the Agents chat. Its title is not stored: selectors read it from the first user message."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents_chat_session"

    def __str__(self):
        return f"Chat {self.pk} of {self.user}"


class ChatRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class ChatMessage(models.Model):
    """One message in a chat session, in the order the session received it."""

    # The (session, id) index below also serves lookups by session alone.
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages", db_index=False)
    role = models.CharField(max_length=16, choices=ChatRole.choices)
    content = models.TextField()
    # The model that wrote an assistant message, as OpenRouter reported it. User messages have none.
    model = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_chat_message"
        ordering = ["id"]
        indexes = [models.Index(fields=["session", "id"], name="agents_chat_msg_session_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=ChatRole.values), name="agents_chat_message_role_valid"),
            models.CheckConstraint(
                condition=models.Q(role=ChatRole.USER, model__isnull=True)
                | models.Q(role=ChatRole.ASSISTANT, model__isnull=False),
                name="agents_chat_message_model_matches_role",
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()} message {self.pk}"

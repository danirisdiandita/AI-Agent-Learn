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
    # Empty for a reply that only calls tools.
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


class ToolCallStatus(models.TextChoices):
    """Where a tool call stands. A call that needs approval starts pending; approved lasts while the tool runs."""

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class ChatToolCall(models.Model):
    """A tool call that an assistant message asked for, with the user's decision and the result the model reads."""

    # The unique (message, call_id) index below also serves lookups by message alone.
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="tool_calls", db_index=False)
    # The provider's id for the call, which the result quotes back to the model.
    call_id = models.CharField(max_length=255)
    name = models.CharField(max_length=64)
    arguments = models.JSONField()
    status = models.CharField(max_length=16, choices=ToolCallStatus.choices, default=ToolCallStatus.PENDING)
    # What goes back to the model as the tool message. Set once the call is settled.
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # When the user approved or declined. Calls the engine settled on its own have none.
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agents_chat_tool_call"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["message", "call_id"], name="agents_chat_tool_call_call_id_unique"),
            models.CheckConstraint(
                condition=models.Q(status__in=ToolCallStatus.values), name="agents_chat_tool_call_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[ToolCallStatus.PENDING, ToolCallStatus.APPROVED], result__isnull=True)
                | models.Q(
                    status__in=[ToolCallStatus.DECLINED, ToolCallStatus.SUCCEEDED, ToolCallStatus.FAILED],
                    result__isnull=False,
                ),
                name="agents_chat_tool_call_result_matches_status",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=ToolCallStatus.PENDING) | models.Q(decided_at__isnull=True),
                name="agents_chat_tool_call_pending_undecided",
            ),
        ]

    def __str__(self):
        return f"{self.name} call {self.pk} ({self.status})"

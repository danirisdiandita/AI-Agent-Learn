from django.contrib import admin

from .models import ChatMessage, ChatSession, ChatToolCall

MESSAGE_FIELDS = ("role", "model", "content", "created_at")


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = MESSAGE_FIELDS
    readonly_fields = MESSAGE_FIELDS
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Shows each chat session with its messages. An admin can delete a session but not edit what was said."""

    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__email",)
    fields = ("user", "created_at", "updated_at")
    readonly_fields = fields
    inlines = [ChatMessageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "model", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "session__user__email")
    fields = ("session", *MESSAGE_FIELDS)
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("session__user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChatToolCall)
class ChatToolCallAdmin(admin.ModelAdmin):
    """Shows each tool call a model asked for, with the user's decision and the result. Nothing here is editable."""

    list_display = ("id", "name", "status", "message", "created_at", "decided_at")
    list_filter = ("name", "status")
    search_fields = ("message__session__user__email",)
    fields = ("message", "call_id", "name", "arguments", "status", "result", "created_at", "decided_at")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("message__session__user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

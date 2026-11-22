from rest_framework import serializers

from ..models import ChatMessage, ChatSession, ChatToolCall


class ChatToolCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatToolCall
        fields = ["id", "name", "arguments", "status", "result", "created_at", "decided_at"]


class ChatMessageSerializer(serializers.ModelSerializer):
    tool_calls = ChatToolCallSerializer(many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "model", "created_at", "tool_calls"]


class ChatSessionSerializer(serializers.ModelSerializer):
    title = serializers.CharField(allow_null=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ["id", "title", "created_at", "updated_at"]


class ChatSessionDetailSerializer(ChatSessionSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = [*ChatSessionSerializer.Meta.fields, "messages"]


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField()

from rest_framework import serializers

from ..models import ChatMessage, ChatSession


class StatelessChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(trim_whitespace=False)


class ChatRequestSerializer(serializers.Serializer):
    messages = StatelessChatMessageSerializer(many=True, allow_empty=False)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "model", "created_at"]


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

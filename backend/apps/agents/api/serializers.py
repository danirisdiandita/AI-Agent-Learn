from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


class TimeZoneField(serializers.CharField):
    """The browser's IANA time zone. It only tells the model the user's local time, so an unknown one becomes UTC."""

    def __init__(self, **kwargs):
        super().__init__(required=False, allow_blank=True, default="UTC", **kwargs)

    def run_validation(self, data=serializers.empty):
        # CharField returns a blank value before to_internal_value, so check the name here.
        name = super().run_validation(data)
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            return "UTC"
        return name


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField()
    time_zone = TimeZoneField()


class DecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    time_zone = TimeZoneField()


class ReplySerializer(serializers.Serializer):
    time_zone = TimeZoneField()

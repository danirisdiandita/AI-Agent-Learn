"""HTTP endpoints for agents. Views parse the request, call a service or selector, and serialize the result.

The endpoints that ask the model answer with a server-sent event stream. Each event's data is JSON:
`user_message` and `assistant_message` (a saved message with its tool calls), `delta` ({text}), `tool_call` (a saved
tool call), `error` ({detail, status}), and finally `done`. A request the chat cannot take now gets a plain JSON error
before any stream starts.
"""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import StreamingHttpResponse
from engine.types import TextDelta
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .. import runtime, selectors, services
from ..models import ChatRole
from .serializers import (
    ChatMessageSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    ChatToolCallSerializer,
    DecisionSerializer,
    ReplySerializer,
    SendMessageSerializer,
)


def owned_session(request, session_id):
    session = selectors.chat_session(user=request.user, session_id=session_id)
    if session is None:
        raise NotFound()
    return session


def validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@api_view(["GET", "POST"])
def chat_sessions(request):
    if request.method == "POST":
        created = services.create_chat_session(user=request.user)
        return Response(ChatSessionDetailSerializer(owned_session(request, created.pk)).data, status=201)
    return Response(ChatSessionSerializer(selectors.chat_sessions(user=request.user), many=True).data)


@api_view(["GET", "DELETE"])
def chat_session(request, session_id):
    if request.method == "DELETE":
        if not services.delete_chat_session(user=request.user, session_id=session_id):
            raise NotFound()
        return Response(status=204)
    return Response(ChatSessionDetailSerializer(owned_session(request, session_id)).data)


@api_view(["POST"])
def chat_messages(request, session_id):
    session = owned_session(request, session_id)
    data = validated(SendMessageSerializer, request)
    return event_stream(lambda: services.send_message(user=request.user, session=session, **data))


@api_view(["POST"])
def chat_reply(request, session_id):
    session = owned_session(request, session_id)
    data = validated(ReplySerializer, request)
    return event_stream(lambda: services.reply(user=request.user, session=session, **data))


@api_view(["POST"])
def tool_call_decision(request, call_id):
    data = validated(DecisionSerializer, request)
    return event_stream(lambda: services.decide_tool_call(user=request.user, call_id=call_id, **data))


def event_stream(start):
    """Starts a service's stream and sends it as server-sent events, or answers its refusal as a JSON error."""
    try:
        events = start()
    except services.Conflict as error:
        return Response({"detail": str(error)}, status=409)
    except runtime.ModelNotConfigured as error:
        return Response({"detail": str(error)}, status=503)
    except services.SessionGone:
        raise NotFound() from None
    if events is None:
        raise NotFound()
    response = StreamingHttpResponse(server_sent_events(events), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    # Tells nginx and similar proxies to pass each event on at once instead of buffering the response.
    response["X-Accel-Buffering"] = "no"
    return response


def server_sent_events(events):
    for event in events:
        name, data = encode(event)
        yield f"event: {name}\ndata: {json.dumps(data, cls=DjangoJSONEncoder)}\n\n"
    yield "event: done\ndata: {}\n\n"


def encode(event):
    match event:
        case TextDelta(text):
            return "delta", {"text": text}
        case services.MessageSaved(message):
            name = "user_message" if message.role == ChatRole.USER else "assistant_message"
            return name, ChatMessageSerializer(message).data
        case services.ToolCallSaved(call):
            return "tool_call", ChatToolCallSerializer(call).data
        case services.ReplyFailed(detail, status):
            return "error", {"detail": detail, "status": status}

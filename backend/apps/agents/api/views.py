"""HTTP endpoints for agents. Views parse the request, call a service or selector, and serialize the result."""

from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .. import openrouter, selectors, services
from .serializers import (
    ChatMessageSerializer,
    ChatRequestSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    SendMessageSerializer,
)


@api_view(["POST"])
def chat(request):
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        reply = openrouter.complete(messages=serializer.validated_data["messages"])
    except openrouter.ChatError as error:
        return Response({"detail": str(error)}, status=error.status)
    return Response({"message": {"role": "assistant", "content": reply.content}})


def owned_session(request, session_id):
    session = selectors.chat_session(user=request.user, session_id=session_id)
    if session is None:
        raise NotFound()
    return session


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
    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        messages = services.send_chat_message(session=session, content=serializer.validated_data["content"])
    except openrouter.ChatError as error:
        return Response({"detail": str(error)}, status=error.status)
    return Response({"messages": ChatMessageSerializer(messages, many=True).data}, status=201)

"""Write operations for agents: chat sessions, their messages, and the tool calls the model asks for.

Each service is a function with keyword-only arguments. The api layer and other apps call these; they never write
models directly.

The model's replies stream. A service that asks the model checks every precondition and saves what the user did
before it returns, so a refusal is a plain exception and nothing is half done. It then returns an iterator of
StreamEvent that runs the model, and saves each model step when the step finishes. No transaction stays open across a
call to the model or to Google.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import chain

from django.db import transaction
from django.utils import timezone

from engine import loop
from engine.types import (
    AssistantMessage,
    Finished,
    Message,
    ModelClient,
    ModelError,
    TextDelta,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    ToolError,
    ToolMessage,
    UserMessage,
)

from . import runtime, tools
from .models import ChatMessage, ChatRole, ChatSession, ChatToolCall, ToolCallStatus

# What the model reads for an approved call that has no result, because the server stopped while the tool ran.
UNKNOWN_OUTCOME = {"error": "The outcome is unknown: the server stopped while the tool was running."}


class Conflict(Exception):
    """The chat does not allow this request now. The message is for the user."""


class SessionGone(Exception):
    """The session was deleted while the request ran."""


@dataclass(frozen=True)
class MessageSaved:
    message: ChatMessage


@dataclass(frozen=True)
class ToolCallSaved:
    call: ChatToolCall


@dataclass(frozen=True)
class ReplyFailed:
    """The model's reply failed. Everything saved before it stays saved. `status` is an HTTP status for the error."""

    detail: str
    status: int


StreamEvent = MessageSaved | TextDelta | ToolCallSaved | ReplyFailed


def create_chat_session(*, user):
    return ChatSession.objects.create(user=user)


def delete_chat_session(*, user, session_id):
    """Deletes one of the user's sessions with its messages. Returns False when the user has no such session."""
    deleted, _ = ChatSession.objects.filter(user=user, pk=session_id).delete()
    return deleted > 0


def send_message(*, user, session, content, time_zone) -> Iterator[StreamEvent]:
    """Saves the user's message and returns the stream of the model's reply, which starts with the saved message.

    Raises Conflict while a tool call in the session waits for a decision, and runtime.ModelNotConfigured when the
    server has no model. Either way nothing is saved.
    """
    client = runtime.model_client()
    with transaction.atomic():
        # Locking the session row first makes a send and a decision on the same session take turns.
        _lock(session)
        if _has_pending_call(session):
            raise Conflict("Approve or decline the tool call first.")
        message = ChatMessage.objects.create(session=session, role=ChatRole.USER, content=content)
    return chain([MessageSaved(message)], _reply(user=user, session=session, client=client, time_zone=time_zone))


def decide_tool_call(*, user, call_id, approve, time_zone) -> Iterator[StreamEvent] | None:
    """Records the user's decision on one of their pending tool calls, runs the tool when they approved it, and returns
    the stream of the model's follow-up, which starts with the decided call.

    Returns None when the user has no such call. Raises Conflict when the call was decided already, which a second
    click on the same card does, and runtime.ModelNotConfigured when the server has no model; then nothing changes.
    The tool runs before this returns, so a client that goes away mid-stream cannot leave an approved call unrun.
    """
    client = runtime.model_client()
    with transaction.atomic():
        call = (
            ChatToolCall.objects.select_for_update(of=("self",))
            .select_related("message__session")
            .filter(pk=call_id, message__session__user=user)
            .first()
        )
        if call is None:
            return None
        if call.status != ToolCallStatus.PENDING:
            raise Conflict("This tool call was decided already.")
        call.status = ToolCallStatus.APPROVED if approve else ToolCallStatus.DECLINED
        call.result = None if approve else {"declined": True}
        call.decided_at = timezone.now()
        call.save()
    if approve:
        try:
            call.result = tools.run_approved(user=user, name=call.name, arguments=call.arguments)
            call.status = ToolCallStatus.SUCCEEDED
        except ToolError as error:
            call.result = {"error": str(error)}
            call.status = ToolCallStatus.FAILED
        call.save(update_fields=["status", "result"])
    session = call.message.session
    return chain([ToolCallSaved(call)], _follow_up(user=user, session=session, client=client, time_zone=time_zone))


def reply(*, user, session, time_zone) -> Iterator[StreamEvent]:
    """Returns the stream of the model's reply to the conversation as it stands, such as after a reply that failed.

    Raises Conflict while a tool call waits for a decision or when the model has answered the last message already,
    and runtime.ModelNotConfigured when the server has no model.
    """
    client = runtime.model_client()
    if _has_pending_call(session):
        raise Conflict("Approve or decline the tool call first.")
    last = ChatMessage.objects.filter(session=session).order_by("-id").first()
    if last is None or (last.role == ChatRole.ASSISTANT and not last.tool_calls.exists()):
        raise Conflict("The model has answered already. Send a new message.")
    return _reply(user=user, session=session, client=client, time_zone=time_zone)


def _follow_up(*, user, session, client, time_zone) -> Iterator[StreamEvent]:
    # A step can ask for several calls. The model answers once the user decided all of them.
    if not _has_pending_call(session):
        yield from _reply(user=user, session=session, client=client, time_zone=time_zone)


def _reply(*, user, session, client: ModelClient, time_zone) -> Iterator[StreamEvent]:
    offered, notes = tools.offer(user=user, time_zone=time_zone)
    messages = [runtime.system_prompt(now=timezone.now(), time_zone=time_zone, notes=notes), *_history(session)]
    settled = []
    try:
        for event in loop.run(client=client, messages=messages, tools=offered):
            match event:
                case TextDelta():
                    yield event
                case ToolCallRequested() | ToolCallCompleted():
                    settled.append(event)
                case Finished():
                    message, calls = _save_step(session=session, finished=event, settled=settled)
                    settled = []
                    yield from (ToolCallSaved(call) for call in calls)
                    yield MessageSaved(message)
    except ModelError as error:
        yield ReplyFailed(str(error), status=502)
    except SessionGone:
        yield ReplyFailed("This chat was deleted.", status=404)


def _history(session) -> list[Message]:
    """The saved conversation as the engine reads it: each reply with its tool calls, then one result per call."""
    history: list[Message] = []
    for message in ChatMessage.objects.filter(session=session).prefetch_related("tool_calls"):
        if message.role == ChatRole.USER:
            history.append(UserMessage(message.content))
            continue
        calls = list(message.tool_calls.all())
        history.append(AssistantMessage(message.content, tuple(ToolCall(c.call_id, c.name, c.arguments) for c in calls)))
        history.extend(ToolMessage(c.call_id, UNKNOWN_OUTCOME if c.result is None else c.result) for c in calls)
    return history


def _save_step(*, session, finished: Finished, settled) -> tuple[ChatMessage, list[ChatToolCall]]:
    with transaction.atomic():
        _lock(session)
        message = ChatMessage.objects.create(
            session=session, role=ChatRole.ASSISTANT, content=finished.content, model=finished.model
        )
        calls = [
            ChatToolCall.objects.create(
                message=message, call_id=call.call_id, name=call.name, arguments=call.arguments, **_outcome(call)
            )
            for call in settled
        ]
    return message, calls


def _outcome(call: ToolCallRequested | ToolCallCompleted) -> dict:
    match call:
        case ToolCallRequested():
            return {"status": ToolCallStatus.PENDING}
        case ToolCallCompleted(failed=True):
            return {"status": ToolCallStatus.FAILED, "result": call.result}
        case ToolCallCompleted():
            return {"status": ToolCallStatus.SUCCEEDED, "result": call.result}


def _lock(session) -> None:
    """Marks the session active, which locks its row until the transaction ends. Raises SessionGone."""
    if not ChatSession.objects.filter(pk=session.pk).update(updated_at=timezone.now()):
        raise SessionGone()


def _has_pending_call(session) -> bool:
    return ChatToolCall.objects.filter(message__session=session, status=ToolCallStatus.PENDING).exists()

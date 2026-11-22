"""Model clients that never reach a network, for tests."""

import time
from collections.abc import Iterator, Sequence

from .types import Finished, Message, ModelError, TextDelta, ToolCall, ToolMessage, ToolSpec, UserMessage


def reply(text: str, *, model: str = "fake/model") -> list:
    """A model step that streams `text` word by word and calls no tool."""
    words = text.split(" ")
    return [*(TextDelta(word if i == 0 else f" {word}") for i, word in enumerate(words) if text), Finished(text, model)]


def calls(*tool_calls: ToolCall, text: str = "", model: str = "fake/model") -> list:
    """A model step that asks for tool calls, after an optional text."""
    return [*([TextDelta(text)] if text else []), Finished(text, model, tuple(tool_calls))]


class FakeClient:
    """Plays model steps back in order, and records the messages and tools that each step was sent.

    A step is a list of events to stream. An exception in the list is raised when the stream reaches it.
    """

    def __init__(self, *steps: list):
        self.steps = list(steps)
        self.sent: list[tuple[list[Message], list[ToolSpec]]] = []

    def stream(self, *, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> Iterator[TextDelta | Finished]:
        self.sent.append((list(messages), list(tools)))
        if not self.steps:
            raise AssertionError("The model was called more often than the test expected.")
        for event in self.steps.pop(0):
            if isinstance(event, Exception):
                raise event
            yield event


class ScriptedClient:
    """Answers from the conversation itself, so the browser e2e can run the chat without a model or a network.

    - After a tool result, it says what happened to the tool call.
    - A message that starts with "Schedule" gets a create_calendar_event call, when that tool is offered.
    - "Fail this reply" breaks off midway the first time this process sees it, and is answered when asked again.
    - Anything else gets a fixed reply.

    Each reply streams a word at a time, slowly enough for a browser to show it arriving.
    """

    model = "e2e/scripted-model"
    failed_once: set[str] = set()

    def stream(self, *, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> Iterator[TextDelta | Finished]:
        last = messages[-1]
        if isinstance(last, UserMessage) and last.content.startswith("Schedule"):
            if any(tool.name == "create_calendar_event" for tool in tools):
                arguments = {"summary": "Design review", "start": "2026-12-01T15:00:00", "end": "2026-12-01T15:30:00"}
                yield Finished("", self.model, (ToolCall(f"scripted-{len(messages)}", "create_calendar_event", arguments),))
                return
            text = "Connect Google Calendar on the Integrations screen first."
        elif isinstance(last, ToolMessage):
            text = "Okay, I did not add it to your calendar." if last.result.get("declined") else "The calendar answered."
        elif isinstance(last, UserMessage) and last.content == "Fail this reply" and last.content not in self.failed_once:
            self.failed_once.add(last.content)
            yield TextDelta("This reply")
            raise ModelError("The scripted model broke off on purpose.")
        else:
            text = "This reply comes from the scripted e2e model, word by word."
        for index, word in enumerate(text.split(" ")):
            time.sleep(0.05)
            yield TextDelta(word if index == 0 else f" {word}")
        yield Finished(text, self.model)

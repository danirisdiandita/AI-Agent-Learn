"""Model clients that never reach a network, for tests."""

from collections.abc import Iterator, Sequence

from .types import Finished, Message, TextDelta, ToolCall, ToolSpec


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

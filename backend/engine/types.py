"""The engine's data: the conversation, the tools, and the events a run yields."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

JSON = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """A tool call the model asked for. `id` is the provider's id, which the result quotes."""

    id: str
    name: str
    arguments: JSON


@dataclass(frozen=True)
class SystemMessage:
    content: str


@dataclass(frozen=True)
class UserMessage:
    content: str


@dataclass(frozen=True)
class AssistantMessage:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolMessage:
    """The result of one tool call, as the model reads it in its next step."""

    call_id: str
    result: JSON


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


@dataclass(frozen=True)
class ToolSpec:
    """What the model sees of a tool: its name, what it does, and a JSON schema of its arguments."""

    name: str
    description: str
    parameters: JSON


class ToolError(Exception):
    """A tool cannot use its arguments, or failed while it ran. The message goes back to the model."""


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    # The engine never runs a tool that needs approval. It stops the run and asks the caller instead.
    requires_approval: bool
    # Checks the model's arguments and returns them cleaned up. Raises ToolError.
    prepare: Callable[[JSON], JSON]
    # Runs the tool with prepared arguments and returns its result. Raises ToolError.
    run: Callable[[JSON], JSON]


@dataclass(frozen=True)
class TextDelta:
    """The next piece of the reply's text."""

    text: str


@dataclass(frozen=True)
class ToolCallRequested:
    """A call to a tool that needs the user's approval, with its prepared arguments. It has not run."""

    call_id: str
    name: str
    arguments: JSON


@dataclass(frozen=True)
class ToolCallCompleted:
    """A call the engine settled without asking: the tool ran, or the call could not be used."""

    call_id: str
    name: str
    arguments: JSON
    result: JSON
    failed: bool


@dataclass(frozen=True)
class Finished:
    """The end of one model step: the whole text, the model that wrote it, and the tool calls it asked for."""

    content: str
    model: str
    tool_calls: tuple[ToolCall, ...] = ()


Event = TextDelta | ToolCallRequested | ToolCallCompleted | Finished


class ModelError(Exception):
    """The model call failed. The message is for the user."""


class ModelClient(Protocol):
    def stream(self, *, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> Iterator[TextDelta | Finished]:
        """Streams one model step: TextDelta events as the text arrives, then one Finished. Raises ModelError."""
        ...

"""The agent loop: call the model, settle the tool calls it asks for, and call it again until it answers."""

from collections.abc import Iterator, Sequence

from .types import (
    AssistantMessage,
    Event,
    Finished,
    Message,
    ModelClient,
    ModelError,
    Tool,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    ToolError,
    ToolMessage,
)

MAX_STEPS = 8


def run(
    *, client: ModelClient, messages: Sequence[Message], tools: Sequence[Tool], max_steps: int = MAX_STEPS
) -> Iterator[Event]:
    """Runs the conversation forward and yields what happens.

    Each model step yields its TextDelta events, then one event per tool call it asked for, then Finished. A call to
    a tool that needs approval yields ToolCallRequested and does not run: the run ends after that step, and the
    caller runs the loop again once the user decided, with the results added to `messages`. Every other call is
    settled at once as ToolCallCompleted, and the model reads its result in the next step.

    Raises ModelError when the model call fails, or when the model still calls tools after `max_steps` steps.
    """
    history = list(messages)
    by_name = {tool.spec.name: tool for tool in tools}
    specs = [tool.spec for tool in tools]
    for _ in range(max_steps):
        finished = None
        for event in client.stream(messages=history, tools=specs):
            if isinstance(event, Finished):
                finished = event
            else:
                yield event
        if finished is None:
            raise ModelError("The model stopped before it finished its reply.")
        settled = [_settle(call, by_name.get(call.name)) for call in finished.tool_calls]
        yield from settled
        yield finished
        if not settled or any(isinstance(call, ToolCallRequested) for call in settled):
            return
        history.append(
            AssistantMessage(finished.content, tuple(ToolCall(c.call_id, c.name, c.arguments) for c in settled))
        )
        history.extend(ToolMessage(call.call_id, call.result) for call in settled)
    raise ModelError(f"The model was still calling tools after {max_steps} steps.")


def _settle(call: ToolCall, tool: Tool | None) -> ToolCallRequested | ToolCallCompleted:
    def failed(arguments, error):
        return ToolCallCompleted(call.id, call.name, arguments, {"error": str(error)}, failed=True)

    if tool is None:
        return failed(call.arguments, f"There is no tool named {call.name}.")
    try:
        arguments = tool.prepare(call.arguments)
    except ToolError as error:
        return failed(call.arguments, error)
    if tool.requires_approval:
        return ToolCallRequested(call.id, call.name, arguments)
    try:
        return ToolCallCompleted(call.id, call.name, arguments, tool.run(arguments), failed=False)
    except ToolError as error:
        return failed(arguments, error)

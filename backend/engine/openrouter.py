"""OpenRouter's chat completions API, streamed, behind the ModelClient interface."""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from .types import (
    AssistantMessage,
    Finished,
    Message,
    ModelError,
    SystemMessage,
    TextDelta,
    ToolCall,
    ToolMessage,
    ToolSpec,
    UserMessage,
)

URL = "https://openrouter.ai/api/v1/chat/completions"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenRouterClient:
    api_key: str
    model: str
    url: str = URL
    # Seconds to wait for each read, so a stream that stalls fails instead of hanging.
    timeout: float = 60

    def stream(self, *, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> Iterator[TextDelta | Finished]:
        body = {"model": self.model, "stream": True, "messages": [_wire(message) for message in messages]}
        if tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            logger.warning("OpenRouter answered HTTP %s: %s", error.code, error.read()[:500])
            raise ModelError(f"OpenRouter refused the request (HTTP {error.code}).") from error
        except OSError as error:
            logger.warning("Cannot reach OpenRouter: %r", error)
            raise ModelError("Cannot reach OpenRouter.") from error
        with response:
            try:
                yield from assemble(sse_data(response), model=self.model)
            except OSError as error:
                logger.warning("The OpenRouter stream broke off: %r", error)
                raise ModelError("The connection to OpenRouter broke off.") from error


def sse_data(lines: Iterable[bytes]) -> Iterator[str]:
    """The data of each server-sent event in a stream of lines, up to OpenRouter's closing [DONE]."""
    data: list[str] = []
    for raw in lines:
        line = raw.decode().rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
        elif not line and data:
            payload, data = "\n".join(data), []
            if payload == "[DONE]":
                return
            yield payload
        # Comments, such as ": OPENROUTER PROCESSING", only keep the connection open.
    if data and (payload := "\n".join(data)) != "[DONE]":
        yield payload


def assemble(payloads: Iterable[str], *, model: str) -> Iterator[TextDelta | Finished]:
    """Turns stream chunks into TextDelta events, then one Finished with the whole text and the tool calls.

    A tool call arrives in pieces that share an index: the id and name first, then its JSON arguments in fragments.
    `model` is the requested model, which Finished names when the stream reports none.
    """
    text: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    reported = None
    for payload in payloads:
        try:
            chunk = json.loads(payload)
        except ValueError as error:
            raise ModelError("OpenRouter sent an unexpected response.") from error
        if not isinstance(chunk, dict):
            raise ModelError("OpenRouter sent an unexpected response.")
        if "error" in chunk:
            logger.warning("OpenRouter stopped the reply: %s", chunk["error"])
            message = chunk["error"].get("message") if isinstance(chunk["error"], dict) else None
            raise ModelError(f"OpenRouter stopped the reply: {message or 'unknown error'}")
        reported = chunk.get("model") or reported
        choices = chunk.get("choices") or []
        delta = (choices[0].get("delta") or {}) if choices else {}
        if content := delta.get("content"):
            text.append(content)
            yield TextDelta(content)
        for part in delta.get("tool_calls") or []:
            index = part.get("index", 0)
            call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
            function = part.get("function") or {}
            call["id"] = call["id"] or part.get("id") or ""
            call["name"] = call["name"] or function.get("name") or ""
            call["arguments"] += function.get("arguments") or ""
    yield Finished(
        content="".join(text),
        model=reported if isinstance(reported, str) else model,
        tool_calls=tuple(_tool_call(index, call) for index, call in sorted(calls.items())),
    )


def _tool_call(index: int, call: dict[str, str]) -> ToolCall:
    try:
        arguments = json.loads(call["arguments"] or "{}")
    except ValueError:
        arguments = None
    if not isinstance(arguments, dict):
        # The tool rejects the empty arguments, and the model reads why in its next step.
        logger.warning("Tool call %s has arguments that are not a JSON object: %r", call["name"], call["arguments"][:500])
        arguments = {}
    return ToolCall(id=call["id"] or f"call_{index}", name=call["name"], arguments=arguments)


def _wire(message: Message) -> dict:
    match message:
        case SystemMessage(content):
            return {"role": "system", "content": content}
        case UserMessage(content):
            return {"role": "user", "content": content}
        case AssistantMessage(content, ()):
            return {"role": "assistant", "content": content}
        case AssistantMessage(content, tool_calls):
            # Some providers reject an empty text part, so a reply that only calls tools sends no content.
            return {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for c in tool_calls
                ],
            }
        case ToolMessage(call_id, result):
            return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)}

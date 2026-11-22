"""What the chat hands the engine besides the conversation: the model client and the system prompt."""

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from engine.openrouter import OpenRouterClient
from engine.types import ModelClient, SystemMessage

DEFAULT_MODEL = "openrouter/auto"


class ModelNotConfigured(Exception):
    """The server has no model to call. The message says how to set one."""


def model_client() -> ModelClient:
    """The client for the model in OPENROUTER_MODEL, with the key in OPENROUTER_API_KEY. Read at call time."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ModelNotConfigured("Set OPENROUTER_API_KEY in .env, then restart the backend.")
    return OpenRouterClient(api_key=api_key, model=os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL)


def system_prompt(*, now: datetime, time_zone: str, notes: Sequence[str]) -> SystemMessage:
    """The instructions the model reads first: the time where the user is, and one note per tool."""
    local = now.astimezone(ZoneInfo(time_zone))
    lines = [
        "You are the assistant in the Nextsci Agents chat. Answer briefly and exactly.",
        f"It is {local:%A %Y-%m-%d %H:%M} in the user's time zone, {time_zone}. "
        f"In UTC it is {now.astimezone(UTC):%Y-%m-%dT%H:%M}Z.",
        *notes,
    ]
    return SystemMessage("\n\n".join(lines))

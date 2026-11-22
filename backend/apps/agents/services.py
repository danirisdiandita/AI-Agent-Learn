"""Write operations for agents: create, update, and delete, with their business rules.

Each service is a function with keyword-only arguments. It validates, writes, and returns model instances.
Wrap multi-step writes in transaction.atomic(). The api layer and other apps call these; they never write models directly.
"""

import json
import os
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"


class ChatError(Exception):
    """A chat request that failed. `status` is the HTTP status the API returns, the message is for the user."""

    def __init__(self, message, *, status):
        super().__init__(message)
        self.status = status


def chat(*, messages):
    """Sends the conversation to OpenRouter and returns the reply as {"role": "assistant", "content": str}."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ChatError("Set OPENROUTER_API_KEY in .env, then restart the backend.", status=503)
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(
            {"model": os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL, "messages": messages}
        ).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        raise ChatError(f"OpenRouter refused the request (HTTP {error.code}).", status=502) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ChatError("Cannot reach OpenRouter.", status=502) from error
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ChatError("OpenRouter sent an unexpected response.", status=502) from error
    return {"role": "assistant", "content": content or ""}

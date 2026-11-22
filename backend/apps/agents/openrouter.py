"""Client for OpenRouter's chat completions API, with the key and model from the environment."""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

import certifi

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"
# python.org builds of Python on macOS ship without CA certificates, so verify against certifi's bundle.
TLS = ssl.create_default_context(cafile=certifi.where())

logger = logging.getLogger(__name__)


class ChatError(Exception):
    """A chat request that failed. `status` is the HTTP status the API returns, the message is for the user."""

    def __init__(self, message, *, status):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Reply:
    content: str
    model: str


def complete(*, messages):
    """Sends the conversation, a list of {"role", "content"} dicts, to OpenRouter and returns its reply.

    The reply names the model that wrote it, as OpenRouter reports it, or the requested model when it reports none.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ChatError("Set OPENROUTER_API_KEY in .env, then restart the backend.", status=503)
    model = os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps({"model": model, "messages": messages}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60, context=TLS) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        logger.warning("OpenRouter answered HTTP %s: %s", error.code, error.read()[:500])
        raise ChatError(f"OpenRouter refused the request (HTTP {error.code}).", status=502) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning("Cannot reach OpenRouter: %r", error)
        raise ChatError("Cannot reach OpenRouter.", status=502) from error
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ChatError("OpenRouter sent an unexpected response.", status=502) from error
    reported = body.get("model")
    return Reply(content=content or "", model=reported if isinstance(reported, str) and reported else model)

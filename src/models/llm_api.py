from __future__ import annotations

import os
import threading
from typing import Any

from openai import OpenAI

API_KEY_ENV = "API_KEY_ENV"                           # environment variable holding the key
BASE_URL = "https://lumen.computes.illinois.edu/v1"   # Lumen's OpenAI-compatible endpoint
MODEL = "deepseek-v4-flash"                           # name callers pass as model=


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

_client: OpenAI | None = None
_client_lock = threading.Lock()


def get_client() -> OpenAI:
    """Return this process's Lumen client.

    The first call builds it from ``API_KEY_ENV``; later calls return the same
    object.
    """
    global _client
    with _client_lock:
        if _client is None:
            api_key = os.environ.get(API_KEY_ENV)
            if not api_key:
                raise RuntimeError(f"set {API_KEY_ENV} to your API key")
            _client = OpenAI(base_url=BASE_URL, api_key=api_key)
        return _client


def chat(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """Send one chat request and return just the answer text.

    ``kwargs`` are passed through to ``chat.completions.create`` (temperature,
    max_tokens, extra_body, ...).
    """
    resp = get_client().chat.completions.create(model=MODEL, messages=messages, **kwargs)
    return resp.choices[0].message.content or ""

"""Provider LLM API (Lumen) for the Web Scraper team.

Thin wrapper over ``models.lumen`` so that older call sites (``chat(messages)``) keep working
while every request goes through the shared API-key pool with rotation (see lumen.py).
"""

from __future__ import annotations

from typing import Any

from models import lumen

BASE_URL = "https://lumen.computes.illinois.edu/v1"   # Lumen's OpenAI-compatible endpoint
MODEL = "deepseek-v4-flash"                           # default model (LUMEN_MODEL overrides)


def get_pool() -> lumen.LumenPool:
    """This process's key pool (built on first use from the environment)."""
    return lumen.get_pool()


def chat(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """Send one chat request through the key pool and return just the answer text."""
    return lumen.chat(messages, **kwargs)


def ask(system_prompt: str, user_text: str, **kwargs: Any) -> str:
    return lumen.ask(system_prompt, user_text, **kwargs)

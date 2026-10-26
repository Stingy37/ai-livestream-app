"""Provider LLM APIs (Claude, OpenAI, ...). Owned by the Web Scraper team.

Shared: other teams may import from here.

LumenClient talks to the Lumen LLM (UIUC) through its OpenAI-compatible API.
The key is read from the LUMEN_API_KEY environment variable only (a local .env
file is loaded if present) — never pass or hard-code it. Error handling follows
qc/simple/ner.py: wait and retry on rate limits, stop at once when the coin
budget is spent, and turn other HTTP errors into a readable message.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

BASE_URL = "https://lumen.computes.illinois.edu/v1"
MODEL = "deepseek-v4-flash"  # the one place the scraper's model name lives
KEY_NAME = "LUMEN_API_KEY"  # the key is read from this environment variable only
RATE_LIMIT_RETRIES = 3  # how many times to wait and retry after an HTTP 429
DEFAULT_WAIT = 5  # seconds to wait if the server does not say how long
TIMEOUT = 60  # seconds per request; the SDK default (10 minutes) would stall a whole scene


class QuotaError(Exception):
    """The Lumen coin budget is spent, so retrying is pointless."""


# Decide what to do about an API error: return seconds to wait, or raise a clear message.
def handle_error(error, attempt):
    status = getattr(error, "status_code", None)
    if status == 429:
        if "insufficient_quota" in str(getattr(error, "body", "")):
            raise QuotaError("Lumen coin budget is spent (insufficient_quota). Stopping.")
        if attempt >= RATE_LIMIT_RETRIES:
            raise RuntimeError("Rate limited too many times. Try again later.")
        headers = getattr(getattr(error, "response", None), "headers", None) or {}
        return float(headers.get("retry-after", DEFAULT_WAIT))
    messages = {
        401: f"401: the API key is missing or wrong. Check {KEY_NAME}.",
        403: "403: model access has not been acknowledged for this key in Lumen.",
        404: "404: model name not found.",
        503: "503: Lumen is temporarily unavailable. Try again later.",
    }
    raise RuntimeError(messages.get(status, f"API error: {type(error).__name__}"))


# Turn a model reply into a dict, tolerating ```json fences. None if it is not a JSON object.
def parse_json(reply):
    text = (reply or "").replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class LumenClient:
    """A small chat client that also counts the tokens it spends."""

    def __init__(self, model=MODEL):
        self.model = model
        self.client = None
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._lock = threading.Lock()  # counters may be updated from worker threads

    def _get_client(self):
        if self.client is None:
            from openai import OpenAI

            try:
                from dotenv import load_dotenv

                load_dotenv()  # fills in variables from .env without overriding real ones
            except ImportError:
                pass
            if not os.environ.get(KEY_NAME):
                raise RuntimeError(f"Set the {KEY_NAME} environment variable first.")
            # max_retries=0: our handle_error decides about retries, so a spent quota is never retried.
            self.client = OpenAI(base_url=BASE_URL, api_key=os.environ[KEY_NAME], max_retries=0, timeout=TIMEOUT)
        return self.client

    # Send one question to the LLM and return the text of its reply.
    def ask(self, system_prompt, user_text, max_tokens=None):
        client = self._get_client()
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
        extra = {"max_tokens": max_tokens} if max_tokens else {}
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                reply = client.chat.completions.create(model=self.model, messages=messages, **extra)
            except Exception as error:
                time.sleep(handle_error(error, attempt))
                continue
            self._count(reply.usage)
            return reply.choices[0].message.content  # never read the reasoning field

    # Ask for a JSON object; one retry if the reply is not valid JSON, else None.
    def ask_json(self, system_prompt, user_text, max_tokens=None):
        for _ in range(2):
            data = parse_json(self.ask(system_prompt, user_text, max_tokens))
            if data is not None:
                return data
            log.warning("The reply was not valid JSON")
        return None

    def _count(self, usage):
        with self._lock:
            self.calls += 1
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0

    # One line for the logs: how much this client has spent so far.
    def usage_summary(self):
        return (
            f"{self.calls} LLM call(s), ~{self.prompt_tokens} prompt + "
            f"~{self.completion_tokens} completion tokens"
        )

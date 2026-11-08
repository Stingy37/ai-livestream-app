"""Lumen (UIUC) LLM access with a pool of API keys and automatic rotation.

Shared by every team: the scraper's agent, QC's NER / NLI judge, and the script QC loop all go
through ``get_pool().chat(...)`` (or ``ask(system, user)``), so one process holds one pool.

Rotation policy (``LumenPool.chat``):

    * keys come from LUMEN_API_KEYS / LUMEN_API_KEY (env) and LUMEN_KEYS_FILE (one per line);
    * requests round-robin over the keys that are not cooling down;
    * 429 rate limit ........ key cools down for Retry-After (default 15 s), next key is tried now;
    * 429 insufficient_quota  key is benched for an hour (its coin budget is spent);
    * 401 / 403 ............. key is benched for the rest of the process (wrong key / model not acknowledged);
    * 5xx / timeouts / connection errors .. key cools down briefly, next key is tried;
    * when every key is cooling down the caller waits for the earliest one (bounded), up to
      ``max_attempts`` tries in total;
    * if the pool is exhausted and ``lumen_local_fallback`` is on, the request is answered by the
      local vLLM model (thinking off) and a warning is logged, so the pipeline keeps moving.

Never logs key values; keys are identified by their index in the pool.
"""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_QUOTA_BENCH_S = 3600.0
_RATE_LIMIT_DEFAULT_S = 15.0
_TRANSIENT_COOLDOWN_S = 8.0
_MAX_SINGLE_WAIT_S = 90.0


class LumenUnavailable(RuntimeError):
    """No key could serve the request and no local fallback was possible."""


@dataclass
class _Key:
    index: int
    value: str
    available_at: float = 0.0        # monotonic time when the key may be used again
    benched: bool = False            # permanently out (401/403)
    requests: int = 0
    failures: int = 0
    note: str = ""


@dataclass
class LumenPool:
    base_url: str
    model: str
    keys: list[_Key]
    timeout: float = 120.0
    max_attempts: int = 12
    local_fallback: bool = True
    _cursor: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _clients: dict[int, Any] = field(default_factory=dict, repr=False)
    stats: dict[str, int] = field(default_factory=lambda: {"requests": 0, "rotations": 0, "local_fallbacks": 0})

    # ---- construction ------------------------------------------------------------------
    @classmethod
    def from_settings(cls, settings=None) -> "LumenPool":
        from config_env import Settings

        s = settings or Settings.from_env()
        raw: list[str] = []
        raw += _split_keys(s.lumen_api_keys)
        raw += _split_keys(os.environ.get("LUMEN_API_KEY", ""))
        raw += _read_keys_file(Path(s.lumen_keys_file))
        # keep order, drop duplicates
        seen, keys = set(), []
        for k in raw:
            if k and k not in seen:
                seen.add(k)
                keys.append(_Key(index=len(keys), value=k))
        pool = cls(base_url=s.lumen_base_url, model=s.lumen_model, keys=keys, timeout=s.lumen_timeout,
                   max_attempts=s.lumen_max_attempts, local_fallback=s.lumen_local_fallback)
        for noisy in ("httpx", "httpx2", "httpcore", "openai"):      # openai 3.x logs through "httpx2"; one line per request is too much
            logging.getLogger(noisy).setLevel(logging.WARNING)
        if not keys:
            log.warning("Lumen key pool is EMPTY (set LUMEN_API_KEYS or %s); local fallback=%s",
                        s.lumen_keys_file, s.lumen_local_fallback)
        else:
            log.info("Lumen key pool: %d key(s), model %s", len(keys), s.lumen_model)
        return pool

    # ---- public API --------------------------------------------------------------------
    def ask(self, system_prompt: str, user_text: str, **kwargs: Any) -> str:
        """QC-style helper: one system + one user message, answer text back."""
        return self.chat([{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_text}], **kwargs)

    def chat(self, messages: list[dict[str, Any]], *, temperature: float | None = None,
             max_tokens: int | None = None, json_mode: bool = False, model: str | None = None,
             allow_fallback: bool = True, **kwargs: Any) -> str:
        """One chat completion through the pool. Returns the answer text (never the reasoning field).

        ``model`` overrides the pool's default model for this request; ``allow_fallback=False`` raises
        LumenUnavailable instead of answering with the local model when every key is down (for callers
        that would rather keep what they have than get a weaker model's answer).
        """
        req: dict[str, Any] = {"messages": messages}
        if temperature is not None:
            req["temperature"] = temperature
        if max_tokens is not None:
            req["max_tokens"] = max_tokens
        if json_mode:
            req["response_format"] = {"type": "json_object"}
        req.update(kwargs)

        last_error: Exception | None = None
        timeouts = 0
        # a request that times out on two different keys is too slow or too large, not unlucky: stop rotating
        max_timeouts = int(os.environ.get("LUMEN_MAX_TIMEOUTS", "2"))
        for attempt in range(self.max_attempts):
            key = self._acquire_key()
            if key is None:
                break
            client = self._client_for(key)
            try:
                with self._lock:
                    key.requests += 1
                    self.stats["requests"] += 1
                resp = client.chat.completions.create(model=model or self.model, timeout=self.timeout, **req)
                text = resp.choices[0].message.content or ""
                if not text and json_mode:
                    # some providers put the json in reasoning when response_format is unsupported; retry plain
                    req.pop("response_format", None)
                    continue
                return text
            except Exception as error:  # noqa: BLE001 - every failure mode is routed by _classify
                last_error = error
                wait = self._classify(key, error)
                with self._lock:
                    key.failures += 1
                    self.stats["rotations"] += 1
                log.warning("Lumen key #%d: %s -> %s (attempt %d/%d)", key.index, _short_error(error),
                            key.note, attempt + 1, self.max_attempts)
                timeouts += "Timeout" in type(error).__name__
                if timeouts >= max_timeouts:
                    log.warning("Lumen: %d timeouts on one request; giving up on Lumen for it", timeouts)
                    break
                if wait:
                    time.sleep(min(wait, _MAX_SINGLE_WAIT_S))
        # pool exhausted
        if self.local_fallback and allow_fallback:
            text = self._local_fallback(messages, temperature, max_tokens)
            if text is not None:
                with self._lock:
                    self.stats["local_fallbacks"] += 1
                    n = self.stats["local_fallbacks"]
                # one warning per process, then a reminder every 100 calls: the fallback is working as designed
                if n == 1 or n % 100 == 0:
                    log.warning("Lumen pool exhausted; answering with the local vLLM model instead (%s) [%d fallback call(s)]",
                                _short_error(last_error) if last_error else "no keys configured", n)
                return text
        raise LumenUnavailable(f"no Lumen key could serve the request ({_short_error(last_error) if last_error else 'no keys'})")

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        return {"model": self.model, "stats": dict(self.stats),
                "keys": [{"index": k.index, "benched": k.benched, "cooling_s": max(0.0, round(k.available_at - now, 1)),
                          "requests": k.requests, "failures": k.failures, "note": k.note} for k in self.keys]}

    # ---- internals ---------------------------------------------------------------------
    def _acquire_key(self) -> _Key | None:
        """Next usable key, round-robin; waits (bounded) when all keys are cooling down."""
        while True:
            with self._lock:
                live = [k for k in self.keys if not k.benched]
                if not live:
                    return None
                now = time.monotonic()
                n = len(self.keys)
                for i in range(n):
                    k = self.keys[(self._cursor + i) % n]
                    if not k.benched and k.available_at <= now:
                        self._cursor = (self._cursor + i + 1) % n
                        return k
                soonest = min(k.available_at for k in live)
                wait = soonest - now
            if wait > _MAX_SINGLE_WAIT_S:
                return None
            time.sleep(max(0.05, wait))

    def _client_for(self, key: _Key):
        with self._lock:
            c = self._clients.get(key.index)
            if c is None:
                from openai import OpenAI

                c = OpenAI(base_url=self.base_url, api_key=key.value, max_retries=0)
                self._clients[key.index] = c
            return c

    def _classify(self, key: _Key, error: Exception) -> float:
        """Update the key's state for this error and return seconds to sleep before the next attempt."""
        status = getattr(error, "status_code", None)
        body = str(getattr(error, "body", "") or "") + " " + str(error)
        now = time.monotonic()
        with self._lock:
            if status == 429:
                if "insufficient_quota" in body or "quota" in body.lower():
                    key.available_at = now + _QUOTA_BENCH_S
                    key.note = "quota spent, benched 1h"
                else:
                    key.available_at = now + _retry_after(error)
                    key.note = f"rate limited, cooling {key.available_at - now:.0f}s"
                return 0.0
            if status in (401, 403):
                key.benched = True
                key.note = f"HTTP {status}: key rejected, benched"
                return 0.0
            if status == 404:
                key.benched = True
                key.note = "HTTP 404: model not found for this key, benched"
                return 0.0
            if status is not None and status >= 500:
                key.available_at = now + _TRANSIENT_COOLDOWN_S
                key.note = f"HTTP {status}, cooling"
                return 1.0
            if status is not None and 400 <= status < 500:
                # a bad request is our fault, not the key's: do not rotate forever
                key.note = f"HTTP {status}"
                raise error
            # connection / timeout / unknown
            key.available_at = now + _TRANSIENT_COOLDOWN_S
            key.note = f"{type(error).__name__}, cooling"
            return 1.0 + random.random()

    def _local_fallback(self, messages, temperature, max_tokens) -> str | None:
        try:
            from models import local_llm_api

            extra = {"chat_template_kwargs": {"enable_thinking": False}}
            kw: dict[str, Any] = {"extra_body": extra}
            kw["temperature"] = 0.2 if temperature is None else temperature
            kw["max_tokens"] = max_tokens or 2048
            return local_llm_api.chat(messages, **kw)
        except Exception as error:  # noqa: BLE001
            log.error("local vLLM fallback failed too: %s", _short_error(error))
            return None


# ---- module-level singleton --------------------------------------------------------------
_pool: LumenPool | None = None
_pool_lock = threading.Lock()


def get_pool(settings=None) -> LumenPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = LumenPool.from_settings(settings)
        return _pool


def ask(system_prompt: str, user_text: str, **kwargs: Any) -> str:
    return get_pool().ask(system_prompt, user_text, **kwargs)


def chat(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    return get_pool().chat(messages, **kwargs)


# ---- helpers ------------------------------------------------------------------------------
def _split_keys(raw: str) -> list[str]:
    return [k.strip() for k in re.split(r"[,\s]+", raw or "") if k.strip()]


def _read_keys_file(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def _retry_after(error: Exception) -> float:
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    try:
        return float(headers.get("retry-after", _RATE_LIMIT_DEFAULT_S))
    except (TypeError, ValueError):
        return _RATE_LIMIT_DEFAULT_S


def _short_error(error: Exception | None) -> str:
    if error is None:
        return ""
    s = str(error).replace("\n", " ")
    return f"{type(error).__name__}: {s[:160]}"

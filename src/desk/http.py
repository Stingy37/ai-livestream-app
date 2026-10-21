"""Small HTTP helper for the desk sources: browser-like UA, timeouts, retries and a short disk cache.

The cache (DESK_CACHE_DIR, default output/desk/cache, TTL DESK_CACHE_TTL_S=120 s) only stops the
same file being downloaded twice inside one update (and by tests); every update sees fresh data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
      "typhoon-desk/1.0")
CACHE_DIR = Path(os.environ.get("DESK_CACHE_DIR", "/home/andyshi2/ai-livestream-app/output/desk/cache"))
CACHE_TTL_S = float(os.environ.get("DESK_CACHE_TTL_S", "120"))
TIMEOUT_S = float(os.environ.get("DESK_HTTP_TIMEOUT_S", "30"))

_local = threading.local()


class FetchError(RuntimeError):
    pass


def _session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()   # requests speaks HTTP/1.1, which NOMADS needs (its HTTP/2 answers are empty)
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
        _local.s = s
    return s


def get_text(url: str, ttl: float | None = None, retries: int = 2) -> str:
    """Body of ``url`` as text; raises FetchError on HTTP errors or empty bodies."""
    ttl = CACHE_TTL_S if ttl is None else ttl
    key = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if ttl > 0 and key.is_file() and time.time() - key.stat().st_mtime < ttl:
        try:
            return json.loads(key.read_text(encoding="utf-8"))["text"]
        except (OSError, ValueError, KeyError):
            pass
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = _session().get(url, timeout=TIMEOUT_S)
            if r.status_code == 404:
                raise FetchError(f"404 {url}")
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            text = r.text
            if not text.strip():
                raise FetchError(f"empty body from {url}")
            if ttl > 0:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = key.with_suffix(".tmp")
                tmp.write_text(json.dumps({"url": url, "text": text}), encoding="utf-8")
                tmp.replace(key)
            return text
        except FetchError:
            raise
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def get_json(url: str, ttl: float | None = None):
    try:
        return json.loads(get_text(url, ttl))
    except ValueError as e:
        raise FetchError(f"{url}: not json ({e})") from e

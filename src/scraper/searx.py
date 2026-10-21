"""SearXNG JSON client (internal to the Web Scraper team).

Talks to the local instance started by scripts/searxng_start.sh (``SEARXNG_URL``, default
http://127.0.0.1:8890 — 8888 is JupyterHub on ICRN). Results are deduplicated by URL and
obviously useless links (social media, video, pdf, images) are dropped before the agent sees them.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8890").rstrip("/")
SEARCH_TIMEOUT = float(os.environ.get("SCRAPE_SEARCH_TIMEOUT", "30"))
MAX_RESULTS_PER_QUERY = int(os.environ.get("SCRAPE_SEARCH_RESULTS", "8"))

SKIP_HOSTS = ("facebook.com", "twitter.com", "x.com", "instagram.com", "tiktok.com", "youtube.com", "youtu.be",
              "reddit.com", "pinterest.com", "linkedin.com", "threads.net", "t.me", "wikipedia.org", "wikimedia.org")
SKIP_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".zip", ".xml", ".kml", ".kmz")


@dataclass
class SearchHit:
    url: str
    title: str
    content: str
    engine: str
    query: str


def usable_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in SKIP_HOSTS):
        return False
    if p.path.lower().endswith(SKIP_SUFFIXES):
        return False
    return True


class SearxClient:
    def __init__(self, base_url: str | None = None, timeout: float = SEARCH_TIMEOUT,
                 max_results: int = MAX_RESULTS_PER_QUERY) -> None:
        self.base_url = (base_url or SEARXNG_URL).rstrip("/")
        self.timeout = timeout
        self.max_results = max_results
        self._session = requests.Session()
        self.stats = {"queries": 0, "results": 0, "errors": 0}

    def available(self) -> bool:
        try:
            r = self._session.get(f"{self.base_url}/search", params={"q": "test", "format": "json"}, timeout=10)
            return r.ok and "results" in r.json()
        except Exception:  # noqa: BLE001
            return False

    def search(self, query: str, time_range: str | None = None, language: str = "en") -> list[SearchHit]:
        """Top results for one query (best first), skipping social/video/pdf links and duplicates."""
        params = {"q": query, "format": "json", "language": language, "safesearch": 0}
        if time_range in ("day", "week", "month", "year"):
            params["time_range"] = time_range
        self.stats["queries"] += 1
        try:
            r = self._session.get(f"{self.base_url}/search", params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            self.stats["errors"] += 1
            log.warning("SearXNG query failed (%r): %s", query, exc)
            return []
        hits, seen = [], set()
        for item in data.get("results", []):
            url = (item.get("url") or "").strip()
            key = _canonical(url)
            if not url or key in seen or not usable_url(url):
                continue
            seen.add(key)
            hits.append(SearchHit(url=url, title=(item.get("title") or "").strip(),
                                  content=re.sub(r"\s+", " ", item.get("content") or "").strip(),
                                  engine=str(item.get("engine") or ""), query=query))
            if len(hits) >= self.max_results:
                break
        self.stats["results"] += len(hits)
        return hits


def _canonical(url: str) -> str:
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    return f"{host}{p.path.rstrip('/')}"

"""Web search for the agentic scraper (internal to the Web Scraper team): SearXNG first, fallbacks when it fails.

Each query goes down this chain and stops at the first step that returns usable results (the search chain from
nirvaanthawani's scraper branch, ee6d8b7, on our client):

  1. SearXNG (free): the local instance started by scripts/searxng_start.sh (``SEARXNG_URL``, default
     http://127.0.0.1:8890; 8888 is JupyterHub on ICRN), through its JSON API.
  2. Tavily (paid, 1 credit per basic search): only if ``TAVILY_API_KEY`` is set, only for a query SearXNG could not
     answer (error, cooling down, or nothing usable), and at most ``SCRAPE_TAVILY_MAX_CREDITS`` searches per process
     (default 20). A wrong key (401) or a spent plan (432 / 433) switches Tavily off for the rest of the process; a
     rate limit (429) skips it for that query only.
  3. ddgs (free, last resort): off unless ``SCRAPE_DDGS_FALLBACK=1`` (and ``pip install ddgs``). It scrapes public
     search engines with randomised browser fingerprints, so it stays opt-in.

One SearXNG error does not switch SearXNG off for the run (that would send every later query to the paid step): after
``SCRAPE_SEARX_FAIL_LIMIT`` errors in a row it is skipped for ``SCRAPE_SEARX_COOLDOWN_S`` seconds, then tried again.
Every step's results go through the same filter: social media, video, pdf and image links are dropped and URLs are
deduplicated before the agent sees them. Every switch is logged and counted in ``stats`` (scrape_report.json).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8890").rstrip("/")
SEARCH_TIMEOUT = float(os.environ.get("SCRAPE_SEARCH_TIMEOUT", "30"))
MAX_RESULTS_PER_QUERY = int(os.environ.get("SCRAPE_SEARCH_RESULTS", "8"))

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_KEY_NAME = "TAVILY_API_KEY"       # read from the environment only
TAVILY_OFF_STATUS = {401: "the key is missing or wrong", 432: "the key or plan limit is spent", 433: "the pay-as-you-go limit is spent"}

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


class TavilyOff(Exception):
    """Tavily cannot be used for the rest of this process (bad key or spent plan)."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class SearxClient:
    """One per scene process; safe to call from the graph's search threads."""

    def __init__(self, base_url: str | None = None, timeout: float = SEARCH_TIMEOUT,
                 max_results: int = MAX_RESULTS_PER_QUERY, tavily_key: str | None = None,
                 tavily_max_credits: int | None = None, ddgs: bool | None = None) -> None:
        self.base_url = (base_url or SEARXNG_URL).rstrip("/")
        self.timeout = timeout
        self.max_results = max_results
        self._session = requests.Session()
        self.tavily_key = (os.environ.get(TAVILY_KEY_NAME, "") if tavily_key is None else tavily_key).strip()
        self.tavily_max_credits = (_env_int("SCRAPE_TAVILY_MAX_CREDITS", 20) if tavily_max_credits is None
                                   else tavily_max_credits)
        self.ddgs_on = os.environ.get("SCRAPE_DDGS_FALLBACK", "") == "1" if ddgs is None else ddgs
        self.searx_fail_limit = max(1, _env_int("SCRAPE_SEARX_FAIL_LIMIT", 2))
        self.searx_cooldown_s = float(os.environ.get("SCRAPE_SEARX_COOLDOWN_S", "120"))
        self._lock = threading.Lock()
        self._searx_fails = 0                 # errors in a row
        self._searx_skip_until = 0.0          # time.monotonic() before which SearXNG is skipped
        self._tavily_off = ""                 # why Tavily was switched off, once it is
        self.stats: dict[str, Any] = {"queries": 0, "results": 0, "errors": 0, "searxng": 0, "tavily": 0, "ddgs": 0,
                                      "tavily_credits": 0, "searx_cooldowns": 0, "no_results": 0}

    # ---- public ----------------------------------------------------------------------------------------------
    def available(self) -> bool:
        """True if web search can run: SearXNG answers, or a fallback step is configured."""
        try:
            r = self._session.get(f"{self.base_url}/search", params={"q": "test", "format": "json"}, timeout=10)
            if r.ok and "results" in r.json():
                return True
        except Exception:  # noqa: BLE001
            pass
        steps = self.fallbacks()
        if steps:
            log.warning("SearXNG at %s is not reachable; searching through the fallback (%s)", self.base_url, ", ".join(steps))
            with self._lock:                  # go straight to the fallback until the cooldown ends, then try SearXNG again
                self._searx_skip_until = time.monotonic() + self.searx_cooldown_s
                self.stats["searx_cooldowns"] += 1
            return True
        return False

    def fallbacks(self) -> list[str]:
        """The fallback steps that can still run, in order."""
        out = []
        if self.tavily_key and not self._tavily_off and self.stats["tavily_credits"] < self.tavily_max_credits:
            out.append("tavily")
        if self.ddgs_on:
            out.append("ddgs")
        return out

    def search(self, query: str, time_range: str | None = None, language: str = "en") -> list[SearchHit]:
        """Top results for one query (best first), skipping social/video/pdf links and duplicates."""
        with self._lock:
            self.stats["queries"] += 1
        if self._searx_ready():
            try:
                hits = self._hits(self._searxng(query, time_range, language), query, engine="")
                self._searx_ok()
                if hits:
                    return self._done(hits, "searxng")
                log.info("SearXNG found nothing usable for %r; trying the fallback", query)
            except Exception as exc:  # noqa: BLE001
                self._searx_failed(exc, query)
        if self._tavily_ready():
            try:
                hits = self._hits(self._tavily(query, time_range), query, engine="tavily")
                if hits:
                    return self._done(hits, "tavily")
                log.info("Tavily found nothing usable for %r", query)
            except TavilyOff as exc:
                with self._lock:
                    self._tavily_off = str(exc)
                log.warning("Tavily is off for the rest of this process: %s", exc)
            except Exception as exc:  # noqa: BLE001 - rate limit, server error, network: this query only
                with self._lock:
                    self.stats["errors"] += 1
                log.warning("Tavily search failed for %r: %s", query, exc)
        if self.ddgs_on:
            try:
                hits = self._hits(self._ddgs(query), query, engine="ddgs")
                if hits:
                    return self._done(hits, "ddgs")
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self.stats["errors"] += 1
                log.warning("ddgs search failed for %r: %s", query, exc)
        with self._lock:
            self.stats["no_results"] += 1
        return []

    # ---- steps -----------------------------------------------------------------------------------------------
    def _searxng(self, query: str, time_range: str | None, language: str) -> list[dict[str, Any]]:
        params = {"q": query, "format": "json", "language": language, "safesearch": 0}
        if time_range in ("day", "week", "month", "year"):
            params["time_range"] = time_range
        r = self._session.get(f"{self.base_url}/search", params=params, timeout=self.timeout)
        if r.status_code == 403:
            raise RuntimeError("403 from SearXNG: its JSON API is off (search.formats in settings.yml)")
        r.raise_for_status()
        return r.json().get("results") or []

    def _tavily(self, query: str, time_range: str | None) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"query": query, "search_depth": "basic",      # basic = 1 credit (advanced is 2)
                                "max_results": max(1, min(self.max_results, 20))}
        if time_range in ("day", "week", "month", "year"):
            body["time_range"] = time_range
        r = self._session.post(TAVILY_URL, json=body, headers={"Authorization": f"Bearer {self.tavily_key}"},
                               timeout=self.timeout)
        if r.status_code in TAVILY_OFF_STATUS:
            raise TavilyOff(f"HTTP {r.status_code} from Tavily: {TAVILY_OFF_STATUS[r.status_code]} (check {TAVILY_KEY_NAME})")
        r.raise_for_status()
        return [{**item, "engine": "tavily"} for item in r.json().get("results") or [] if isinstance(item, dict)]

    def _ddgs(self, query: str) -> list[dict[str, Any]]:
        from ddgs import DDGS                 # optional dependency, imported only when the step is switched on

        items = DDGS(timeout=int(self.timeout)).text(query, max_results=self.max_results)
        return [{"url": i.get("href"), "title": i.get("title"), "content": i.get("body"), "engine": "ddgs"}
                for i in items or [] if isinstance(i, dict)]

    # ---- bookkeeping -----------------------------------------------------------------------------------------
    def _hits(self, items: list[dict[str, Any]], query: str, engine: str) -> list[SearchHit]:
        hits, seen = [], set()
        for item in items:
            url = (item.get("url") or "").strip()
            key = _canonical(url)
            if not url or key in seen or not usable_url(url):
                continue
            seen.add(key)
            hits.append(SearchHit(url=url, title=(item.get("title") or "").strip(),
                                  content=re.sub(r"\s+", " ", item.get("content") or "").strip(),
                                  engine=str(item.get("engine") or engine), query=query))
            if len(hits) >= self.max_results:
                break
        return hits

    def _done(self, hits: list[SearchHit], step: str) -> list[SearchHit]:
        with self._lock:
            self.stats[step] += 1
            self.stats["results"] += len(hits)
        return hits

    def _searx_ready(self) -> bool:
        with self._lock:
            return time.monotonic() >= self._searx_skip_until

    def _searx_ok(self) -> None:
        with self._lock:
            self._searx_fails = 0

    def _searx_failed(self, exc: Exception, query: str) -> None:
        with self._lock:
            self.stats["errors"] += 1
            self._searx_fails += 1
            cool = self._searx_fails >= self.searx_fail_limit
            if cool:
                self._searx_fails = 0
                self._searx_skip_until = time.monotonic() + self.searx_cooldown_s
                self.stats["searx_cooldowns"] += 1
        log.warning("SearXNG query failed (%r): %s", query, exc)
        if cool:
            log.warning("SearXNG failed %d times in a row; skipping it for %.0f s", self.searx_fail_limit, self.searx_cooldown_s)

    def _tavily_ready(self) -> bool:
        """Reserves one credit when Tavily may run for this query."""
        with self._lock:
            if not self.tavily_key or self._tavily_off:
                return False
            if self.stats["tavily_credits"] < self.tavily_max_credits:
                self.stats["tavily_credits"] += 1
                return True
            self._tavily_off = f"credit cap reached ({self.tavily_max_credits} searches this process)"
        log.warning("Tavily %s; no more paid searches", self._tavily_off)
        return False


def _canonical(url: str) -> str:
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    return f"{host}{p.path.rstrip('/')}"

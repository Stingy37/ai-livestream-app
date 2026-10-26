"""Web search for the scraper agent: SearXNG first, DuckDuckGo (ddgs) as a fallback.

SearXNG is read from the SEARXNG_URL environment variable and queried through
its JSON API (``/search?q=...&format=json``). That API only answers if the
instance lists ``json`` under ``search.formats`` in its settings.yml — many
public instances do not, so see ``searxng/README.md`` for running one locally.

If SEARXNG_URL is unset or the instance fails, the search falls back to the
``ddgs`` package and says so in the logs. If that fails too, the search returns
no results rather than raising; the agent treats that as "nothing found".
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

URL_NAME = "SEARXNG_URL"  # the SearXNG base URL is read from this environment variable only
TIMEOUT = 15  # seconds
DDGS_BACKENDS = ("auto", "bing, yahoo")  # tried in order until one returns results
CACHE_TTL = 3600  # seconds a query's results are reused, so regeneration cycles do not search again
MIN_INTERVAL = 1.0  # seconds between two searches that go out to the network, so they never come in a burst


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    engine: str  # "searxng" or "ddgs"


class Searcher:
    """Runs searches for one scene. Remembers if SearXNG is down so it is not retried every query."""

    def __init__(self, base_url=None, max_results=10, cache_dir=None):
        from scraper import fetch

        self.base_url = (base_url if base_url is not None else os.environ.get(URL_NAME, "")).rstrip("/")
        self.max_results = max_results
        self.cache_dir = Path(cache_dir) if cache_dir is not None else fetch.CACHE_DIR / "search"
        self.last_search = 0.0
        self.searxng_ok = bool(self.base_url)
        if not self.searxng_ok:
            log.warning("%s is not set; searching with DuckDuckGo (ddgs) instead of SearXNG.", URL_NAME)

    # Results for one query: from the cache if recent, otherwise from the network (throttled).
    def search(self, query):
        path = self.cache_dir / (hashlib.sha256(f"{self.max_results}|{query}".encode()).hexdigest() + ".json")
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - entry["saved"] <= CACHE_TTL:
                return [SearchResult(**r) for r in entry["results"]]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        wait = self.last_search + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        results = self._search_network(query)
        self.last_search = time.monotonic()
        if results:  # an empty answer may be a temporary block, so it is not remembered
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps({"saved": time.time(), "results": [asdict(r) for r in results]}), encoding="utf-8")
                os.replace(tmp, path)
            except OSError as error:
                log.info("could not cache search results: %s", error)
        return results

    def _search_network(self, query):
        if self.searxng_ok:
            try:
                return self.searxng(query)
            except Exception as error:
                self.searxng_ok = False
                log.warning("SearXNG search failed (%s); using DuckDuckGo (ddgs) for the rest of this run.", error)
        try:
            return self.ddgs(query)
        except Exception as error:
            log.warning("DuckDuckGo search failed too (%s); no results for %r.", error, query)
            return []

    def searxng(self, query):
        import httpx

        response = httpx.get(
            f"{self.base_url}/search",
            params={"q": query, "format": "json"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        if response.status_code == 403:
            raise RuntimeError("403 from SearXNG: the JSON API is disabled on this instance (search.formats)")
        response.raise_for_status()
        results = []
        for item in response.json().get("results", []):
            if item.get("url"):
                results.append(SearchResult(item["url"], item.get("title", ""), item.get("content", ""), "searxng"))
        return results[: self.max_results]

    def ddgs(self, query):
        from ddgs import DDGS

        # "auto" often fails when DuckDuckGo itself rate-limits us; Bing and Yahoo (also via ddgs) usually still answer.
        for backend in DDGS_BACKENDS:
            try:
                items = DDGS(timeout=TIMEOUT).text(query, max_results=self.max_results, backend=backend)
            except Exception as error:
                last_error = error
                continue
            return [SearchResult(i["href"], i.get("title", ""), i.get("body", ""), "ddgs") for i in items if i.get("href")]
        raise last_error

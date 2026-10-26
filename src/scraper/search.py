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

import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)

URL_NAME = "SEARXNG_URL"  # the SearXNG base URL is read from this environment variable only
TIMEOUT = 15  # seconds


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    engine: str  # "searxng" or "ddgs"


class Searcher:
    """Runs searches for one scene. Remembers if SearXNG is down so it is not retried every query."""

    def __init__(self, base_url=None, max_results=10):
        self.base_url = (base_url if base_url is not None else os.environ.get(URL_NAME, "")).rstrip("/")
        self.max_results = max_results
        self.searxng_ok = bool(self.base_url)
        if not self.searxng_ok:
            log.warning("%s is not set; searching with DuckDuckGo (ddgs) instead of SearXNG.", URL_NAME)

    def search(self, query):
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

        items = DDGS(timeout=TIMEOUT).text(query, max_results=self.max_results)
        return [SearchResult(i["href"], i.get("title", ""), i.get("body", ""), "ddgs") for i in items if i.get("href")]

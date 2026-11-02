"""Web search for the scraper agent: cheap first, paid only when needed.

Each query goes down this chain and stops at the first step that returns results:

  1. SearXNG (free) — read from the SEARXNG_URL environment variable and queried
     through its JSON API (``/search?q=...&format=json``). That API only answers
     if the instance lists ``json`` under ``search.formats`` in its settings.yml —
     many public instances do not, so see ``searxng/README.md`` for running one.
  2. Tavily (paid, 1 credit per search) — only if TAVILY_API_KEY is set, and only
     for queries SearXNG could not answer. A spent plan or bad key switches Tavily
     off for the rest of the run instead of being retried.
  3. ddgs (free, last resort) — scrapes public search engines, so it may be
     rate-limited; used when neither of the above is configured or both failed.

Every switch is logged. If all three fail the search returns no results rather
than raising; the agent treats that as "nothing found". Results are cached for
CACHE_TTL seconds whichever step produced them, so a query is never paid twice.
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
TAVILY_KEY_NAME = "TAVILY_API_KEY"  # the Tavily key is read from this environment variable only
TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = 15  # seconds
# ddgs backends, tried in order until one returns results. Only names ddgs lists as available work
# (an unknown name is silently replaced by "auto"); in live tests only yahoo answered when "auto" did not.
DDGS_BACKENDS = ("auto", "yahoo")
CACHE_TTL = 3600  # seconds a query's results are reused, so regeneration cycles do not search again
MIN_INTERVAL = 1.0  # seconds between two searches that go out to the network, so they never come in a burst


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    engine: str  # "searxng", "tavily" or "ddgs"


class TavilyOff(Exception):
    """Tavily cannot be used for the rest of this run (bad key or credits spent)."""


class Searcher:
    """Runs searches for one scene. Remembers which steps are down so they are not retried every query."""

    def __init__(self, base_url=None, max_results=10, cache_dir=None, tavily_key=None):
        from scraper import fetch

        self.base_url = (base_url if base_url is not None else os.environ.get(URL_NAME, "")).rstrip("/")
        self.tavily_key = tavily_key if tavily_key is not None else os.environ.get(TAVILY_KEY_NAME, "")
        self.max_results = max_results
        self.cache_dir = Path(cache_dir) if cache_dir is not None else fetch.CACHE_DIR / "search"
        self.last_search = 0.0
        self.searxng_ok = bool(self.base_url)
        self.tavily_ok = bool(self.tavily_key)
        self.tavily_calls = 0  # each is 1 Tavily credit
        if not self.searxng_ok:
            log.warning("%s is not set; skipping SearXNG.", URL_NAME)
        if not self.tavily_ok:
            log.info("%s is not set; no paid Tavily fallback, ddgs is the last resort.", TAVILY_KEY_NAME)

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

    # The chain: SearXNG (free) -> Tavily (paid) -> ddgs (free, last resort).
    def _search_network(self, query):
        if self.searxng_ok:
            try:
                results = self.searxng(query)
                if results:
                    return results
                log.info("SearXNG found nothing for %r; trying the next search step.", query)
            except Exception as error:
                self.searxng_ok = False  # an instance that errors once is likely down for the whole run
                log.warning("SearXNG search failed (%s); skipping it for the rest of this run.", error)
        if self.tavily_ok:
            try:
                results = self.tavily(query)
                if results:
                    return results
                log.info("Tavily found nothing for %r; trying ddgs.", query)
            except TavilyOff as error:
                self.tavily_ok = False
                log.warning("%s Skipping Tavily for the rest of this run.", error)
            except Exception as error:  # rate limit, server error, network: skip for this query only
                log.warning("Tavily search failed (%s); trying ddgs for %r.", error, query)
        try:
            return self.ddgs(query)
        except Exception as error:
            log.warning("ddgs search failed too (%s); no results for %r.", error, query)
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
        for item in response.json().get("results") or []:
            if isinstance(item, dict) and item.get("url"):
                results.append(SearchResult(item["url"], item.get("title") or "", item.get("content") or "", "searxng"))
        return results[: self.max_results]

    def tavily(self, query):
        import httpx

        self.tavily_calls += 1
        response = httpx.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {self.tavily_key}"},
            # "basic" is 1 credit; set explicitly so it never becomes a 2-credit "advanced" search.
            json={"query": query, "search_depth": "basic", "max_results": min(self.max_results, 20)},
            timeout=TIMEOUT,
        )
        if response.status_code == 401:
            raise TavilyOff(f"401 from Tavily: the key is missing or wrong. Check {TAVILY_KEY_NAME}.")
        if response.status_code in (432, 433):
            raise TavilyOff(f"{response.status_code} from Tavily: the plan or pay-as-you-go credit limit is spent.")
        response.raise_for_status()
        results = []
        for item in response.json().get("results") or []:
            if isinstance(item, dict) and item.get("url"):
                results.append(SearchResult(item["url"], item.get("title") or "", item.get("content") or "", "tavily"))
        return results

    def ddgs(self, query):
        from ddgs import DDGS

        # "auto" often fails when DuckDuckGo itself rate-limits us; Yahoo (also via ddgs) usually still answers.
        last_error = RuntimeError("no results")
        for backend in DDGS_BACKENDS:
            try:
                items = DDGS(timeout=TIMEOUT).text(query, max_results=self.max_results, backend=backend)
            except Exception as error:
                last_error = error
                continue
            results = [
                SearchResult(i["href"], i.get("title") or "", i.get("body") or "", "ddgs")
                for i in items or [] if isinstance(i, dict) and i.get("href")
            ]
            if results:  # an empty answer is treated like a failure: try the next backend
                return results
        raise last_error

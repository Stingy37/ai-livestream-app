"""Contains methods for scraping and extracting information from the open web.

From a scene's title and description, uses an agentic framework (LangGraph, local only) to find and
scrape websites relevant to a scene: a ReAct search node (SearXNG + Trafilatura), a verify node that
checks every claim (agency conflicts and stale data only) and three experts (typhoon, emergency,
citizen) that steer the next search round when the verified pool misses the baseline.
Output is the cleaned, unsplit, complete text of each website's main body, used for downstream
scoring, splitting, clustering, and retrieval.

Web search is used when ``Scene.sources`` is empty, or when the scene's ``node_key`` (or id) is listed
in ``SCRAPE_WEB_SEARCH_SCENES`` (comma-separated; main.py fills it from the config's ``do_web_search``).
Otherwise only the user-supplied URLs and links on those pages (same site) are fetched.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from contracts import Scene, ScrapedDocument

log = logging.getLogger(__name__)


def web_search_allowed(scene: Scene) -> bool:
    listed = {s.strip() for s in os.environ.get("SCRAPE_WEB_SEARCH_SCENES", "").split(",") if s.strip()}
    return not scene.sources or scene.node_key in listed or scene.id in listed


class WebScraper:
    """Public interface for turning a scene into a set of cleaned source documents.

    One instance per scene process. Concurrency *inside* a scene — fetching and
    cleaning the sites, parallel model calls — is threads owned by this class; the caller
    has already given us our own process.

    Two source paths, chosen per scene by ``Scene.sources`` (and SCRAPE_WEB_SEARCH_SCENES):

      * ``sources`` non-empty — the user supplied those URLs; they are the input set and
        the agent may only follow links on those pages (unless web search is switched on
        for the scene).
      * ``sources`` empty — the agent discovers its own sites from the scene's title and
        topic description through SearXNG.

    Either way the output shape is identical, so downstream stages never branch
    on which path produced a document. After ``gather`` the full graph trace is in
    ``last_report`` (see ``_report``); main.py writes it next to the documents.
    """

    def __init__(self, max_threads: int = 8) -> None:
        self.max_threads = max_threads
        self.last_report: dict[str, Any] = {}
        self._graph = None
        self._searx = None
        self._fetcher = None

    # Built lazily: importing langgraph / trafilatura / the model client only when a scene is scraped.
    def _ensure(self) -> None:
        if self._graph is not None:
            return
        from models import lumen

        from scraper.fetch import Fetcher
        from scraper.graph import ScrapeGraph
        from scraper.searx import SearxClient

        timeout = float(os.environ.get("SCRAPE_TIMEOUT", "25"))
        self._fetcher = Fetcher(max_threads=self.max_threads, timeout=timeout)
        searx = SearxClient()
        if searx.available():
            self._searx = searx
        else:
            log.warning("SearXNG at %s is not reachable; web search is off for this process", searx.base_url)
            self._searx = None
        pool = lumen.get_pool()

        def ask(system: str, user: str, **kw: Any) -> str:
            kw.setdefault("temperature", 0.1)
            kw.setdefault("max_tokens", 1500)
            return pool.ask(system, user, **kw)

        self._graph = ScrapeGraph(self._fetcher, self._searx, ask, max_threads=self.max_threads)

    def gather(self, scene: Scene) -> list[ScrapedDocument]:
        """Find, fetch, and clean this scene's source documents.

        Returns documents in relevance order (user sources first), cleaned and ready for
        scoring. Partial failure is expected and tolerated: a site that will not fetch or
        yields no main body is dropped from the result (and listed in ``last_report``)
        rather than raising. Returning an empty list is how this reports that nothing
        usable was found — the caller decides that is fatal for the scene.
        """
        self._ensure()
        t0 = time.time()
        scene_dict = {"id": scene.id, "node_key": scene.node_key, "title": scene.title, "topic": scene.topic_description,
                      "sources": list(scene.sources), "language": scene.language}
        web_search = web_search_allowed(scene)
        try:
            state = self._graph.run(scene_dict, web_search)
        except Exception as exc:  # noqa: BLE001 - a graph crash must still leave a report behind
            log.exception("scraper graph failed for %r", scene.title)
            self.last_report = {"scene_id": scene.id, "node_key": scene.node_key, "error": f"{type(exc).__name__}: {exc}",
                                "web_search": web_search, "seconds": round(time.time() - t0, 1)}
            return []
        docs: list[ScrapedDocument] = [d for d in state.get("docs", []) if d.main_text.strip()]
        self.last_report = self._report(scene, state, web_search, time.time() - t0)
        if not docs:
            log.warning("no usable documents for %r", scene.title)
        return docs

    def _report(self, scene: Scene, state: dict[str, Any], web_search: bool, seconds: float) -> dict[str, Any]:
        """Everything main.py writes to scrape_report.json (json-serialisable only)."""
        from models import lumen

        verify = state.get("verify")
        docs = state.get("docs", [])
        return {
            "scene_id": scene.id, "node_key": scene.node_key, "title": scene.title,
            "web_search": web_search, "searxng": self._searx.base_url if self._searx else None,
            "rounds": state.get("round", 0), "end_reason": state.get("end_reason", ""),
            "queries": list(state.get("queries_done", [])),
            "urls_fetched": [d.url for d in docs],
            "urls_failed": [e["url"] for e in state.get("fetch_log", []) if not e["ok"]],
            "fetch_log": state.get("fetch_log", []),
            "documents": [{"url": d.url, "source_name": d.source_name, "title": d.title, "chars": len(d.main_text),
                           "published_at": d.published_at.isoformat() if d.published_at else None,
                           "discovered_by": d.metadata.get("discovered_by"), "verify": d.metadata.get("verify")} for d in docs],
            "checklist": state.get("checklist", []),
            "sufficient": state.get("sufficient", False), "missing": state.get("missing", []),
            "verify": verify.to_dict() if verify else None,
            "baseline": state.get("baseline", {}),
            "experts": state.get("experts", []),
            "trace": state.get("trace", []),
            "fetch_stats": dict(self._fetcher.stats) if self._fetcher else {},
            "search_stats": dict(self._searx.stats) if self._searx else {},
            "lumen": lumen.get_pool().status(),
            "seconds": round(seconds, 1),
        }

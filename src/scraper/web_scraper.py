"""Contains methods for scraping and extracting information from the open web.

From a scene's title and description, uses an agentic framework to find and scrape websites relevant to a scene.
Output is cleaned, unsplit text of the website's main body, used for downstream scoring, splitting, clustering, and retrieval.
"""

from __future__ import annotations

import logging
import os

from contracts import Scene, ScrapedDocument

log = logging.getLogger(__name__)

# Heavy libraries (langgraph, trafilatura, httpx, openai) are imported inside
# gather(), so importing this module stays cheap and dependency-free — the
# contract tests import it with nothing but pytest installed.


class WebScraper:
    """Public interface for turning a scene into a set of cleaned source documents.

    One instance per scene process. Concurrency *inside* a scene — fetching and
    cleaning the sites — is threads owned by this class; the caller has
    already given us our own process.

    Two source paths, chosen per scene by ``Scene.sources``:

      * ``sources`` non-empty — the user supplied those URLs; they are the input
        set and no discovery happens.
      * ``sources`` empty — the agent discovers its own sites from the scene's
        title and topic description.

    Either way the output shape is identical, so downstream stages never branch
    on which path produced a document.
    """

    def __init__(self, max_threads: int = 8) -> None:
        self.max_threads = max(1, max_threads)

    def gather(self, scene: Scene) -> list[ScrapedDocument]:
        """Find, fetch, and clean this scene's source documents.

        Returns documents in relevance order, cleaned and ready for scoring.
        Partial failure is expected and tolerated: a site that will not fetch or
        yields no main body is dropped from the result rather than raising, so a
        scene with several sources survives losing one. Returning an empty list
        is how this reports that nothing usable was found — the caller decides
        that is fatal for the scene.

        Where the agent already has parsing capability, the main body comes back
        directly from the agent rather than through a separate extraction pass.
        """
        from models.llm_api import KEY_NAME, LumenClient
        from scraper.fetch import Fetcher

        _load_dotenv()
        fetcher = Fetcher(max_threads=self.max_threads)
        llm = None
        try:
            if scene.sources:
                log.info("%s: fetching %d user-supplied source(s), no discovery", scene.title, len(scene.sources))
                documents = fetcher.fetch_all(scene.sources)
                for document in documents:
                    document.metadata.setdefault("discovered_via", "user")
            else:
                from scraper.agent import DiscoveryAgent
                from scraper.search import Searcher

                if os.environ.get(KEY_NAME):
                    llm = LumenClient()
                else:
                    log.warning("%s is not set; discovering sources without the LLM.", KEY_NAME)
                log.info("%s: no sources given, discovering sites", scene.title)
                documents = DiscoveryAgent(Searcher(), fetcher, llm).run(scene)
        except Exception:  # an empty result is how we report failure; the caller decides it is fatal
            log.exception("%s: scraping failed", scene.title)
            documents = []
        finally:
            fetcher.client.close()

        log.info("%s: %d usable document(s)", scene.title, len(documents))
        if llm is not None:
            log.info("%s: LLM usage this run: %s", scene.title, llm.usage_summary())
        return documents


def _load_dotenv() -> None:
    """Fill in LUMEN_API_KEY / SEARXNG_URL from a local .env, never overriding real environment variables."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()

"""Contains methods for scraping and extracting information from the open web.

From a scene's title and description, uses an agentic framework to find and scrape websites relevant to a scene.
Output is cleaned, unsplit text of the website's main body, used for downstream splitting, clustering, and retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from modules.graph import Scene


@dataclass
class ScrapedDocument:
    """One website's cleaned main body, plus what we know about where it came from.

    ``main_text`` is cleaned but deliberately *unsplit* — sentence splitting is
    cluster.py's job. Metadata is best-effort: a missing publication date makes
    the recency term of ``website_score`` weaker but does not invalidate the
    document.

    Picklable: this is returned across a process boundary to the scene worker.
    """

    url: str
    title: str
    main_text: str
    rank: int  # position in the agent's relevance ordering, 0 = best
    published_at: datetime | None = None
    author: str | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WebScraper:
    """Public interface for turning a scene into a set of cleaned source documents.

    One instance per scene process. Concurrency *inside* a scene — fetching and
    cleaning the top-k sites — is threads owned by this class; the caller has
    already given us our own process.

    Two source paths, chosen per scene by ``Scene.do_web_search``:

      * ``do_web_search`` false — the user supplied ``Scene.sources``; those URLs
        are the input set and no discovery happens.
      * ``do_web_search`` true — the agent discovers its own top-k sites from the
        scene's title and topic description.

    Either way the output shape is identical, so downstream stages never branch
    on which path produced a document.
    """

    def __init__(self, top_k: int = 8, max_threads: int = 8) -> None:
        raise NotImplementedError

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
        raise NotImplementedError

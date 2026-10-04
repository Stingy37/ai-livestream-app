"""Source documents: Web Scraper → QC website scoring → RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScrapedDocument:
    """One website's cleaned main body, plus what we know about where it came from.

    Produced by ``scraper.WebScraper.gather``; consumed by
    ``qc.WebsiteScorer.score_documents``.

    ``main_text`` is cleaned but deliberately *unsplit* — sentence splitting is
    RAG's job. Metadata is best-effort: real pages often lack a publication date
    or author, so those are ``None`` when missing rather than invented.
    """

    url: str
    title: str
    main_text: str  # cleaned, unsplit
    source_name: str  # issuing agency, e.g. "JTWC"
    published_at: datetime | None = None
    author: str | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredDocument:
    """A scraped document with its ``website_score`` and the accept/reject call.

    Produced by ``qc.WebsiteScorer.score_documents`` (one per input document,
    rejects included); main.py passes only the accepted ones on to RAG.

    ``score_components`` keeps the individual terms (e.g. agreement, recency)
    rather than only the weighted total, so a rejection can be explained in a
    warning instead of being an opaque number.
    """

    document: ScrapedDocument
    score: float  # 0–1, higher is better
    score_components: dict[str, float] = field(default_factory=dict)  # each 0–1
    accepted: bool = False

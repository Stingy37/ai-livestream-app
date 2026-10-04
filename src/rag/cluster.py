"""Contains methods and the class representing the cluster formed from HDBSCAN of the scrapped sentences.

Methods pertaining to building and interacting with the cluster class go here, including splitting the sentences,
converting into their embedding representation, HDBSCAN algorithm + hyperparameters, exemplar lookup, returning a cluster, etc.

However, logic for building the lookup for querying this cluster belongs in retrieval.py.
Internal to the RAG team — the only public entry point is ``rag.Retriever``.
We expect ths module to recieve sentences (for initial building) and cluster query requests (for querying the built clusters,) and output a HDBSCAN class which acts as a interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from contracts import ScrapedDocument, Sentence


@dataclass
class ClusterMatch:
    """One cluster returned for one query vector, with its member sentences."""

    cluster_id: int
    similarity: float
    exemplar: str
    sentences: list[Sentence]


class SentenceSplitter:
    """Regex-level splitter producing the flat sentence pool for a scene.

    Deliberately cheap and deterministic — no model call. The pool is scene-wide
    rather than per-document: sentences from every accepted document go into one
    pool so that a later cluster can span sources, which is what makes
    cross-source agreement visible to retrieval.
    """

    def __init__(self, min_chars: int = 0) -> None:
        raise NotImplementedError

    def split(self, documents: Sequence[ScrapedDocument]) -> list[Sentence]:
        """Flatten documents into one ordered pool of sentences."""
        raise NotImplementedError


class SentenceClusterIndex:
    """The fitted HDBSCAN index over one scene's sentence pool.

    This is the interface object the module docstring calls for: built once from
    sentences, then queried by retrieval.py with embedded query vectors.

    Never leaves RAG's process: ``Retriever.retrieve`` builds and queries it in
    the same call, so it does not need to be picklable. ``save``/``load`` are
    optional conveniences (e.g. caching an index between experiments), not part
    of the team contract.
    """

    @classmethod
    def build(cls, sentences: Sequence[Sentence]) -> "SentenceClusterIndex":
        """Embed the sentence pool and fit the modified HDBSCAN over it.

        Hyperparameters and the modifications to stock HDBSCAN live in this
        module; the caller supplies only sentences.
        """
        raise NotImplementedError

    def query(self, vectors: Sequence[Sequence[float]], top_k: int) -> list[list[ClusterMatch]]:
        """Look up the top-k clusters per query vector, matched on exemplars.

        Returns one ranked ``ClusterMatch`` list per input vector, positionally
        aligned with ``vectors`` — retrieval.py relies on that alignment to map
        results back to the decomposed query that produced them.
        """
        raise NotImplementedError

    def exemplars(self) -> dict[int, str]:
        """The representative sentence per cluster, keyed by cluster id."""
        raise NotImplementedError

    def save(self, path: Path) -> None:
        """Persist the fitted index so another process can load it."""
        raise NotImplementedError

    @classmethod
    def load(cls, path: Path) -> "SentenceClusterIndex":
        """Rehydrate an index persisted by ``save``."""
        raise NotImplementedError

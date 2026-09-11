"""Contains methods and the class representing the cluster formed from HDBSCAN of the scrapped sentences.

Methods pertaining to building and interacting with the cluster class go here, including splitting the sentences,
converting into their embedding representation, HDBSCAN algorithm + hyperparameters, exemplar lookup, returning a cluster, etc.

However, logic for building the lookup for querying this cluster belongs in retrieval.py.
We expect ths module to recieve sentences (for initial building) and cluster query requests (for querying the built clusters,) and output a HDBSCAN class which acts as a interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from modules.webscrapper import ScrapedDocument


@dataclass
class Sentence:
    """One sentence in a scene's flat pool, with provenance kept attached.

    Provenance survives all the way into the generated script's context so the
    writer can attribute claims to a source agency, and so ``script_score`` can
    tell which document a contradicting fact came from.
    """

    text: str
    source_url: str
    document_index: int  # position within the scene's staged document list
    sentence_index: int  # position within that document, for ordering


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

    Does *not* cross a process boundary as a live object — stage 2 persists it
    via ``database.Database`` and stage 3 loads it back in its own process, so
    ``save``/``load`` are part of the contract rather than a convenience.
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

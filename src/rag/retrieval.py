"""Contains methods for building the multi-coverage lookup queries for our HDBSCAN cluster, given a input query.

Uses a small LLM to split a scene title + scene description into specific items needed to answer the scene,
and embeds them into vector representations for cluster exemplar lookup.
Concatates and returns a structured list of relevant sentences from the retrieved cluster(s).

Example:
    1. Input: "This scene summarizes the forecasted local impacts to the local region of Cebu"  + sys_instruction + scene_title
                        [ LLM: "What information is needed to generate the for this scene" ]
    2. LLM Query decomposition: "Wind forecasts," "local terrain," "Cebu warnings" etc.
                         [ HDBSCAN query with the decomposed query vectors ]
    3. Structured output:
        relevant_sentences = {
                                "decomposed query one": decomposed query one relevant sentences
                                "decomposed query two": decomposed query two relevant sentences
                            }
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts import RetrievedContext, Scene, ScoredDocument
from rag.cluster import SentenceClusterIndex, SentenceSplitter


@dataclass
class SearchQuery:
    """One decomposed information need, with its embedding for cluster lookup."""

    text: str
    vector: list[float] = field(default_factory=list)


class Retriever:
    """Turns a scene into the structured context its script will be written from.

    The RAG team's single public entry point. Takes the accepted documents,
    builds the scene's cluster index internally (``SentenceSplitter`` →
    ``SentenceClusterIndex``), decomposes the scene into queries with a small
    LLM, and looks them up by semantic search over cluster exemplars.
    """

    def __init__(self, top_k: int = 5) -> None:
        raise NotImplementedError

    def decompose(self, scene: Scene) -> list[SearchQuery]:
        """Split the scene into the specific information items needed to answer it.

        Driven by the scene's title, topic description, and system instructions —
        the same three fields the writer will work from, so retrieval targets
        what the script actually has to say.
        """
        raise NotImplementedError

    def retrieve(self, scene: Scene, documents: list[ScoredDocument]) -> RetrievedContext:
        """Build the index from ``documents``, decompose, query, and assemble the grouped result.

        ``documents`` are the accepted ``ScoredDocument``s from QC website
        scoring; ``score`` is available for weighting or tie-breaking.

        Deduplicates sentences that several queries pull in, while keeping each
        under every query that matched it.
        """
        raise NotImplementedError

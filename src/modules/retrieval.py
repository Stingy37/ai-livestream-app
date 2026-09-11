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

from modules.cluster import Sentence, SentenceClusterIndex
from modules.graph import Scene


@dataclass
class SearchQuery:
    """One decomposed information need, with its embedding for cluster lookup."""

    text: str
    vector: list[float] = field(default_factory=list)


@dataclass
class RetrievedContext:
    """The structured retrieval output: sentences grouped by the query that found them.

    Grouping is load-bearing rather than cosmetic. Keeping the decomposed query
    attached tells the writer *why* each block of sentences is present, and
    keeps coverage visible — an empty group is a question the sources did not
    answer, which is worth surfacing rather than silently flattening away.
    """

    scene_id: str
    relevant_sentences: dict[str, list[Sentence]] = field(default_factory=dict)

    def is_populated(self) -> bool:
        """True if any query returned at least one sentence.

        The caller treats an unpopulated context as fatal for the scene: there
        is nothing to write a script from.
        """
        raise NotImplementedError

    def unanswered_queries(self) -> list[str]:
        """Decomposed queries that matched nothing — coverage gaps worth warning on."""
        raise NotImplementedError


class Retriever:
    """Turns a scene into the structured context its script will be written from.

    Wraps one scene's fitted cluster index. Decomposition uses a small LLM;
    lookup is semantic search over cluster exemplars with the decomposed query
    vectors.
    """

    def __init__(self, index: SentenceClusterIndex, top_k: int = 5) -> None:
        raise NotImplementedError

    def decompose(self, scene: Scene) -> list[SearchQuery]:
        """Split the scene into the specific information items needed to answer it.

        Driven by the scene's title, topic description, and system instructions —
        the same three fields the writer will work from, so retrieval targets
        what the script actually has to say.
        """
        raise NotImplementedError

    def retrieve(self, scene: Scene) -> RetrievedContext:
        """Decompose, query the cluster index, and assemble the grouped result.

        Deduplicates sentences that several queries pull in, while keeping each
        under every query that matched it.
        """
        raise NotImplementedError

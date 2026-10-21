"""Context retrieval for one scene: build the sentence index and retrieve once up front.

The dynamic-RAG script writer retrieves iteratively *during* generation (writer/dynrag.py) from
the index this module saves under the run folder. ``Retriever.retrieve`` is the safety net the
user asked for: one retrieval at the beginning of generation with the original scene description
as the query, returned as the contract's ``RetrievedContext`` and spliced into the writer's first
``<information>`` block.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from config_env import Settings
from contracts import RetrievedContext, Scene, ScoredDocument, Sentence
from rag.cluster import SentenceClusterIndex, SentenceSplitter

log = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """One information need, with its embedding for index lookup."""

    text: str
    vector: list[float] = field(default_factory=list)


class Retriever:
    """The RAG team's single public entry point."""

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k
        self.settings = Settings.from_env()
        self.splitter = SentenceSplitter(min_chars=self.settings.min_sentence_chars)
        self.last_index: SentenceClusterIndex | None = None

    def decompose(self, scene: Scene) -> list[SearchQuery]:
        """The up-front queries: the scene description itself (the user's safety-net query) and its title."""
        queries = [scene.topic_description.strip()]
        if scene.title and scene.title.lower() not in scene.topic_description.lower():
            queries.append(f"{scene.title}: {scene.topic_description.strip()}")
        return [SearchQuery(text=q) for q in queries]

    def retrieve(self, scene: Scene, documents: list[ScoredDocument]) -> RetrievedContext:
        """Build the index from the accepted documents, save it, and retrieve for each query."""
        accepted = [d for d in documents if d.accepted] or list(documents)
        docs = [d.document for d in accepted]
        sentences = self.splitter.split(docs)
        titles = {i: d.title for i, d in enumerate(docs)}
        index = SentenceClusterIndex.build(sentences, titles=titles)
        index_dir = self.settings.layout().index_dir(scene.id)
        index.save(index_dir)
        self.last_index = index
        log.info("[rag] %s: %d sentences from %d documents -> %s", scene.title, len(sentences), len(docs), index_dir)

        queries = self.decompose(scene)
        context = RetrievedContext(scene_id=scene.id)
        if not sentences:
            for q in queries:
                context.relevant_sentences[q.text] = []
            return context
        hits = index.search_texts([q.text for q in queries], top_k=self.top_k)
        for q, row in zip(queries, hits):
            seen: set[tuple[str, int]] = set()
            picked: list[Sentence] = []
            for m in row:
                key = (m.sentence.source_url, m.sentence.sentence_index)
                if key in seen:
                    continue
                seen.add(key)
                picked.append(m.sentence)
            context.relevant_sentences[q.text] = picked
        return context

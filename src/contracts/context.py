"""Retrieved context: RAG → script writer and QC harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Sentence:
    """One sentence from a source document, with provenance kept attached.

    Provenance survives all the way into the writer's context so the script can
    attribute claims to a source agency ("JTWC reports…") and prefer the most
    recent advisory, and so QC can tell which document a contradicting fact
    came from.
    """

    text: str
    source_url: str
    source_name: str
    published_at: datetime | None
    document_index: int  # position within the scene's accepted document list
    sentence_index: int  # position within that document, for ordering


@dataclass
class RetrievedContext:
    """The structured retrieval output: sentences grouped by the query that found them.

    Produced by ``rag.Retriever.retrieve``; consumed by ``writer.ScriptWriter``
    and ``qc.ScriptHarness``.

    ``relevant_sentences`` maps each decomposed query → its sentences, best
    first. Grouping is load-bearing: it tells the writer *why* each block is
    present, and an empty group is a question the sources did not answer.
    """

    scene_id: str
    relevant_sentences: dict[str, list[Sentence]] = field(default_factory=dict)

    def is_populated(self) -> bool:
        """True if any query returned at least one sentence."""
        return any(self.relevant_sentences.values())

    def unanswered_queries(self) -> list[str]:
        """Decomposed queries that matched nothing — coverage gaps worth warning on."""
        return [query for query, sentences in self.relevant_sentences.items() if not sentences]

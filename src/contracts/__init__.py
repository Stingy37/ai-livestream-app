"""The team interface contract, as code.

Every dataclass that crosses a team boundary lives here and nowhere else. Both
sides of a hand-off import the same class, so a mismatch fails loudly at import
or in ``tests/contracts`` instead of silently disagreeing with the docs.

Source of truth for *what* these contain is the "Team Interface Contract" page
in Notion; this package is the enforced copy of it. Changing anything in here
changes the contract — it needs agreement from the upstream and downstream
teams first.

Hand-offs, in pipeline order:

    Scene                          config  → every stage
    list[ScrapedDocument]          Web Scraper  → QC website scoring
    list[ScoredDocument]           QC website scoring → RAG (accepted only)
    RetrievedContext               RAG → script writer / QC harness
    LLMOutput                      script writer → QC harness
    ScriptOutcome                  QC harness → Audio
    AudioAsset                     Audio → broadcast loop

All of these cross a process boundary, so they must stay picklable: plain
fields only — no open clients, loaded models, generators, or lambdas.
"""

from contracts.audio import AudioAsset
from contracts.context import RetrievedContext, Sentence
from contracts.documents import ScoredDocument, ScrapedDocument
from contracts.scene import Scene
from contracts.script import LLMOutput, ScriptOutcome, ScriptScore

__all__ = [
    "AudioAsset",
    "LLMOutput",
    "RetrievedContext",
    "Scene",
    "ScoredDocument",
    "ScrapedDocument",
    "ScriptOutcome",
    "ScriptScore",
    "Sentence",
]

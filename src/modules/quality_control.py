"""Includes methods for scoring the various parts of the pipeline, including website-to-website scores, internal consistency of a script, etc.

Specifically, we define our scoring algorithms here, as well as associated hyperpameters such as weights.
Additionally we also include our scoring harness(s) as class(es) here, serving as public interfaces for the rest of the pipeline to interact with our scoring mechanisms.

We use the following algorithms to score:
        1. website_score = W1 * website_rank + W2 * cross_website entity agreement + W3 * recency
                - for websites within a group, after initial web-scrapping and before clustering

        2. script_score = f(entity 1) + f(entity 2) + f(entity 3) + .... + f(entity N)
                - for all entities within a document, where f(entity) is the amount of contradicting facts a certain entity has.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modules.graph import Scene
from modules.retrieval import RetrievedContext
from modules.webscrapper import ScrapedDocument


# ─────────────────────────────────────────────────────────────────────────────
# 1. Website scoring — after scraping, before clustering
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScoredDocument:
    """A scraped document with its ``website_score`` and the accept/reject call.

    ``components`` keeps the individual terms (rank, cross-website agreement,
    recency) rather than only the weighted total, so a rejection can be
    explained to the user in a warning instead of being an opaque number.
    """

    document: ScrapedDocument
    score: float
    components: dict[str, float] = field(default_factory=dict)
    accepted: bool = False


class WebsiteScorer:
    """Scores a scene's scraped documents against each other and applies the threshold.

    Scoring is inherently *group-wise*, not per-document: the cross-website
    entity agreement term compares each document against its peers, so this
    takes the whole set at once and cannot be called incrementally as documents
    arrive.
    """

    def __init__(self, threshold: float = 0.0, weights: dict[str, float] | None = None) -> None:
        raise NotImplementedError

    def score_documents(self, documents: list[ScrapedDocument]) -> list[ScoredDocument]:
        """Score every document in the group and mark which clear the threshold.

        Returns one ``ScoredDocument`` per input document, including rejected
        ones — the caller needs the rejects to warn the user about dropped
        sources.
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 2. Script scoring — internal consistency of a generated script
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScriptScore:
    """Result of ``script_score`` over one candidate script.

    The total is a contradiction count summed per entity, so **lower is better**
    and zero is a clean script. ``per_entity`` keeps the breakdown so the judge
    and the rewrite feedback can point at the specific entity in dispute.
    """

    total: float
    per_entity: dict[str, float] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    passes_threshold: bool = False


class ScriptScorer:
    """The cheap, deterministic consistency check run before any judge call.

    Resolves entities with the NER + coreference models, then classifies fact
    pairs per entity with the NLI cross-encoder, counting contradictions. Cheap
    relative to an LLM judge, which is the whole point: most scripts should
    clear this and never reach the judge.
    """

    def __init__(self, threshold: float = 0.0) -> None:
        raise NotImplementedError

    def score(self, script: str, context: RetrievedContext) -> ScriptScore:
        """Score one script for internal contradictions.

        The retrieved context is passed in because a claim is only contradictory
        relative to the source material it was drawn from.
        """
        raise NotImplementedError


@dataclass
class JudgeVerdict:
    """The LLM judge's ruling on a script that ``script_score`` flagged.

    ``contradictions_confirmed`` false means the cheap score produced a false
    positive and the script is acceptable as written. True means the rewrite
    loop continues, and ``feedback`` is what the writer gets to work from.
    """

    contradictions_confirmed: bool
    feedback: str | None = None
    disputed_entities: list[str] = field(default_factory=list)


class LLMJudge:
    """Second opinion on scripts that failed the cheap threshold.

    Only ever invoked on a failing script — it exists to catch ``script_score``
    false positives and to turn a genuine contradiction into actionable rewrite
    feedback, not to re-score everything.
    """

    def __init__(self, model: str | None = None) -> None:
        raise NotImplementedError

    def review(self, script: str, context: RetrievedContext, score: ScriptScore) -> JudgeVerdict:
        """Adjudicate the contradictions ``score`` claims to have found."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 3. Script harness — owns the write / score / judge / rewrite loop
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScriptOutcome:
    """What the harness hands back after the loop settles."""

    script: str
    score: ScriptScore
    accepted: bool
    attempts: int
    warnings: list[str] = field(default_factory=list)


class ScriptHarness:
    """Produces an acceptable script for one scene, iterating until it has one.

    Script *generation* has no module of its own because it is a plain LLM call
    with the scene's system instructions — it lives here, inside the loop that
    owns it, rather than being handed in as a callback. Keeping the writer and
    the scorers behind one interface is also what lets main.py stay free of
    model calls: it asks for a script and stores what comes back.

    The loop, per attempt:

        write(context, feedback, previous) → script_score → LLMJudge

    and it exits on the first of:

        1. ``script_score`` clears the threshold           → accept
        2. the judge overturns the score                   → accept
        3. ``max_attempts`` exhausted                      → best candidate by score

    Case 3 always returns *something*: the least-contradictory candidate seen,
    with a warning recorded. ``accepted`` is false only if no candidate could be
    produced at all, which the caller treats as fatal for the scene.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        scorer: ScriptScorer | None = None,
        judge: LLMJudge | None = None,
    ) -> None:
        raise NotImplementedError

    def produce(self, scene: Scene, context: RetrievedContext) -> ScriptOutcome:
        """Run the loop until the script is acceptable or the budget is spent.

        Every attempt re-uses the same ``context`` — retrieval does not re-run —
        and a rewrite additionally receives the judge's feedback plus the script
        that earned it, so the writer can see what it is fixing.

        Uses ``scene.script_model`` for the write call and
        ``scene.system_instructions`` as the system prompt.
        """
        raise NotImplementedError

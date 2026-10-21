"""Quality Control stages, built on the QC team's simple contradiction engine (qc/simple).

    Part A  WebsiteScorer.score_documents   cross-source contradictions over the scraped pool;
                                            agreement score per document; dynamic threshold that
                                            removes at most QC_MAX_REMOVED_FRACTION of the pool
    Part B  ScriptScorer.score              a script against itself (--within-source) and against
                                            the facts Part A flagged as disputed
            ScriptHarness.produce           write -> score -> rewrite with the flagged pairs attached,
                                            up to max_attempts; the best draft wins if none passes

QC never rewrites website text or scripts; it only scores, flags and removes.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config_env import Settings, read_json, write_json
from contracts import (
    LLMOutput,
    RetrievedContext,
    Scene,
    ScoredDocument,
    ScrapedDocument,
    ScriptOutcome,
    ScriptScore,
)
from qc.lumen_bridge import SceneQC
from qc.simple.script import ScriptChecker
from writer import ScriptWriter

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Website scoring — after scraping, before retrieval (Part A)
# ─────────────────────────────────────────────────────────────────────────────


class WebsiteScorer:
    """Scores a scene's scraped documents against each other and applies the dynamic threshold.

    ``threshold`` is the *base* threshold: a document with agreement at or above it is never
    removed. The effective threshold is lowered so that at most ``max_removed_fraction`` of the
    pool is removed, whatever the pool's overall fitness. Documents that were never compared
    (no shared entity with any other source) keep a neutral score and are kept.
    """

    def __init__(self, threshold: float | None = None, weights: dict[str, float] | None = None,
                 max_removed_fraction: float | None = None, scene_dir: Path | None = None) -> None:
        self.settings = Settings.from_env()
        self.threshold = self.settings.qc_base_threshold if threshold is None else threshold
        self.max_removed_fraction = (self.settings.qc_max_removed_fraction if max_removed_fraction is None
                                     else max_removed_fraction)
        self.weights = weights or {"agreement": 0.7, "recency": 0.2, "rank": 0.1}
        self.scene_dir = scene_dir
        self.last_result: dict[str, Any] = {}

    def score_documents(self, documents: list[ScrapedDocument]) -> list[ScoredDocument]:
        """Score every document in the group and mark which clear the dynamic threshold."""
        if not documents:
            return []
        for i, d in enumerate(documents):
            d.metadata.setdefault("qc_id", f"doc_{i:02d}")
        ids = [d.metadata["qc_id"] for d in documents]
        qc = SceneQC(self.scene_dir, self.settings)
        try:
            result = qc.pipeline.run(documents, cross_source=True)
        finally:
            qc.save_caches()
        agreement: dict[str, float | None] = result["agreement"]

        n = len(documents)
        max_removed = int(math.floor(self.max_removed_fraction * n))
        scored_vals = sorted(v for v in agreement.values() if v is not None)
        effective = self.threshold
        if max_removed < len(scored_vals):
            # the (max_removed+1)-th lowest score: only documents strictly below it can be removed
            effective = min(self.threshold, scored_vals[max_removed])
        candidates = sorted((agreement[i], i) for i in ids if agreement.get(i) is not None and agreement[i] < effective)
        removed = {i for _, i in candidates[:max_removed]}
        if len(removed) >= n:  # never empty the pool
            removed = set(list(removed)[: n - 1])

        now = datetime.now(timezone.utc)
        out: list[ScoredDocument] = []
        for rank, d in enumerate(documents):
            qid = d.metadata["qc_id"]
            agree = agreement.get(qid)
            comps = {"agreement": 1.0 if agree is None else float(agree), "recency": _recency(d, now),
                     "rank": 1.0 - rank / max(1, n), "compared": 0.0 if agree is None else 1.0}
            score = sum(self.weights[k] * comps[k] for k in ("agreement", "recency", "rank"))
            flagged_here = [f for f in result["flagged_pairs"]
                            if f["sentence_a"]["source_id"] == qid or f["sentence_b"]["source_id"] == qid]
            d.metadata["qc"] = {"agreement": agree, "flagged_pairs": len(flagged_here),
                                "blamed": sum(1 for f in flagged_here for b in f.get("blamed", []) if b[0] == qid)}
            out.append(ScoredDocument(document=d, score=round(score, 4), score_components=comps,
                                      accepted=qid not in removed))
        self.last_result = {
            "pairs_compared": result["pairs_compared"], "flagged_pairs": result["flagged_pairs"],
            "agreement": agreement, "base_threshold": self.threshold, "effective_threshold": effective,
            "max_removed": max_removed, "removed": sorted(removed),
            "documents": [{"qc_id": d.metadata["qc_id"], "url": d.url, "source_name": d.source_name,
                           "agreement": agreement.get(d.metadata["qc_id"]), "accepted": d.metadata["qc_id"] not in removed}
                          for d in documents],
            "stats": qc.stats(),
        }
        log.info("[qc-a] %d docs, %d pairs compared, %d flagged, threshold %.2f (base %.2f), removed %d (max %d)",
                 n, result["pairs_compared"], len(result["flagged_pairs"]), effective, self.threshold, len(removed), max_removed)
        return out


def _recency(d: ScrapedDocument, now: datetime) -> float:
    """1.0 for data under 6 h old, decaying linearly to 0 at 48 h; 0.5 when the age is unknown."""
    if not d.published_at:
        return 0.5
    pub = d.published_at if d.published_at.tzinfo else d.published_at.replace(tzinfo=timezone.utc)
    age_h = max(0.0, (now - pub).total_seconds() / 3600)
    if age_h <= 6:
        return 1.0
    return max(0.0, 1.0 - (age_h - 6) / 42)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Script scoring — Part B
# ─────────────────────────────────────────────────────────────────────────────

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "by", "and", "for", "with", "from", "is", "are", "was",
         "were", "will", "that", "this", "it", "its", "as", "be", "has", "have", "over", "near", "than", "about"}


class ScriptScorer:
    """Part B: internal contradictions of a script + statements of facts Part A flagged as disputed."""

    ENTAIL_THRESHOLD = 0.85

    def __init__(self, threshold: float | None = None, scene_dir: Path | None = None, qc: SceneQC | None = None) -> None:
        self.settings = Settings.from_env()
        self.threshold = self.settings.script_score_threshold if threshold is None else threshold
        self.scene_dir = scene_dir
        self.qc = qc
        self.last_details: dict[str, Any] = {}

    def _qc(self, scene_id: str) -> SceneQC:
        if self.qc is None:
            self.qc = SceneQC(self.scene_dir or self.settings.layout().scene_dir(scene_id), self.settings)
        return self.qc

    def disputed_facts(self, scene_id: str) -> list[dict[str, Any]]:
        """Sentences Part A flagged for this scene (from qc_part_a.json), with agency, entity and reason."""
        path = self.settings.layout().qc_part_a(scene_id)
        if not path.is_file():
            return []
        try:
            data = read_json(path)
        except (OSError, ValueError):
            return []
        agency = {d["qc_id"]: d.get("source_name", "") for d in data.get("documents", [])}
        out, seen = [], set()
        for f in data.get("flagged_pairs", []):
            for side in ("sentence_a", "sentence_b"):
                s = f[side]
                if s["text"] in seen:
                    continue
                seen.add(s["text"])
                out.append({"text": s["text"], "source_id": s["source_id"], "agency": agency.get(s["source_id"], ""),
                            "entity": f.get("entity", ""), "reason": f.get("reason", "")})
        return out

    def score(self, script: LLMOutput, context: RetrievedContext) -> ScriptScore:
        qc = self._qc(context.scene_id)
        checker = ScriptChecker(qc.pipeline, threshold=self.threshold)
        try:
            within = checker.score(script)
            disputed_msgs, disputed_entities = self._check_disputed(qc, checker, script, context.scene_id)
        finally:
            qc.save_caches()
        unsupported_msgs = self._check_unsupported_figures(qc, checker, script, context.scene_id)
        alert_msgs = self._check_unsupported_alerts(qc, checker, script, context.scene_id)
        unsupported_msgs += alert_msgs
        per_entity = dict(within.per_entity)
        for e in disputed_entities:
            per_entity[e] = per_entity.get(e, 0) + 1
        if unsupported_msgs:
            per_entity["unsupported figure"] = per_entity.get("unsupported figure", 0) + len(unsupported_msgs)
        contradictions = list(within.contradictions) + disputed_msgs + unsupported_msgs
        total = float(len(contradictions))
        if alert_msgs:
            per_entity["unsupported alert"] = len(alert_msgs)
        self.last_details = {"within_total": within.total, "disputed_total": len(disputed_msgs), "alert_total": len(alert_msgs),
                             "unsupported_total": len(unsupported_msgs), "stats": qc.stats()}
        return ScriptScore(total=total, per_entity=per_entity, contradictions=contradictions,
                           passes_threshold=total <= self.threshold)

    def _check_disputed(self, qc: SceneQC, checker: ScriptChecker, script: LLMOutput, scene_id: str) -> tuple[list[str], list[str]]:
        """Script sentences that restate a disputed figure without saying who reported it.

        A figure the sources disagree on may be read on air only when it is attributed to the
        agency that reported it. Attribution carries over a short span: a sentence counts as
        attributed when the agency is named in it or in one of the two sentences before it (spoken
        copy attributes per paragraph, not per sentence). Figures that are merely *different* from
        another agency's or another valid time's figure are not flagged here: that is normal for
        forecasts, and invented figures are caught by the unsupported-figure check.
        """
        facts = self.disputed_facts(scene_id)
        if not facts:
            return [], []
        sentences = qc.ner.split_sentences(checker.clean_script(script.llm_output))
        msgs, entities = [], []
        for i, s in enumerate(sentences):
            s_words = _content_words(s)
            window = " ".join(sentences[max(0, i - 2):i + 1]).lower()
            for f in facts:
                if not (s_words & _content_words(f["text"])):
                    continue  # nothing in common: cannot be about the same fact
                if _mentions(window, f["agency"]):
                    continue  # attributed: fine, whatever the other agencies say
                fwd = qc.nli.probabilities(f["text"], s)
                bwd = qc.nli.probabilities(s, f["text"])
                if max(fwd.get("entailment", 0.0), bwd.get("entailment", 0.0)) >= self.ENTAIL_THRESHOLD:
                    label = f["entity"] or "disputed fact"
                    msgs.append(f'{label}: "{s}" states a figure the sources dispute without naming the agency '
                                f'("{f["text"][:160]}" from {f["agency"] or f["source_id"]}; {f["reason"]})')
                    entities.append(label)
                    break  # one flag per script sentence is enough
        return msgs, entities

    def _check_unsupported_figures(self, qc: SceneQC, checker: ScriptChecker, script: LLMOutput, scene_id: str) -> list[str]:
        """Every number the script reads out must occur in the scene's source sentences (never invent figures).

        Deterministic and cheap: the numeric tokens of each script sentence are looked up in the
        sentence pool the writer retrieved from (index/sentences.json). Times of day, years and
        small counting numbers are ignored; a sentence with an unknown figure is flagged once.
        """
        pool = _source_numbers(self.settings.layout().index_dir(scene_id) / "sentences.json")
        if pool is None:
            return []
        msgs = []
        for sent in qc.ner.split_sentences(checker.clean_script(script.llm_output)):
            missing = [n for n in _figures(sent) if n not in pool]
            if missing:
                msgs.append(f'unsupported figure: "{sent}" states {", ".join(missing[:4])}, which no source reports')
        return msgs


    def _check_unsupported_alerts(self, qc: SceneQC, checker: ScriptChecker, script: LLMOutput, scene_id: str) -> list[str]:
        """Every warning, advisory, evacuation, cancellation or closure the script says is in effect must be named
        by a source sentence (English or Japanese wording). Invented alerts are the most harmful error a safety
        broadcast can make, so these are hard failures (see ``ALERT_PREFIX``): the scene is rewritten, else dropped."""
        try:
            rows = read_json(self.settings.layout().index_dir(scene_id) / "sentences.json")["sentences"]
        except (OSError, ValueError, KeyError):
            return []
        pool = " ".join(r["text"] for r in rows).lower()
        msgs = []
        for sent in qc.ner.split_sentences(checker.clean_script(script.llm_output)):
            low = sent.lower()
            if _NEGATED.search(low):
                continue                                   # "no warning has been issued" states nothing new
            for name, (claim, evidence) in ALERTS.items():
                if claim.search(low) and not evidence.search(pool):
                    msgs.append(f'{ALERT_PREFIX}: "{sent}" says a {name} is in effect, which no source reports')
                    break
        return msgs


ALERT_PREFIX = "unsupported alert"
_NEGATED = re.compile(r"\b(no|not|none|without|yet to|has not|have not|hasn't|haven't|neither|nor|if|unless|may|might|could|possible|possibly|in case)\b")   # denied or conditional
ALERTS = {   # name: (claim in the script, evidence in the sources)
    "storm warning": (re.compile(r"\b(storm|violent wind|typhoon) warnings?\b"), re.compile(r"storm warning|violent wind warning|暴風警報|暴風特別警報")),
    "high wave warning": (re.compile(r"\bhigh[- ]wave warnings?\b"), re.compile(r"high[- ]wave warning|波浪警報")),
    "storm surge warning": (re.compile(r"\bstorm[- ]surge warnings?\b"), re.compile(r"storm[- ]surge warning|高潮警報")),
    "heavy rain warning": (re.compile(r"\bheavy[- ]rain(fall)? warnings?\b"), re.compile(r"heavy[- ]rain(fall)? warning|大雨警報")),
    "flood warning": (re.compile(r"\bflood(ing)? warnings?\b"), re.compile(r"flood(ing)? warning|洪水警報")),
    "emergency warning": (re.compile(r"\b(emergency|special) warnings?\b"), re.compile(r"emergency warning|special warning|特別警報")),
    "gale or strong wind advisory": (re.compile(r"\b(gale|strong[- ]wind) (advisory|warning)\b"), re.compile(r"gale (advisory|warning)|strong[- ]wind advisory|強風注意報|gale warning")),
    "high wave advisory": (re.compile(r"\bhigh[- ]wave advisor(y|ies)\b"), re.compile(r"high[- ]wave advisory|波浪注意報")),
    "heavy rain advisory": (re.compile(r"\bheavy[- ]rain advisor(y|ies)\b"), re.compile(r"heavy[- ]rain advisory|大雨注意報")),
    "storm surge advisory": (re.compile(r"\bstorm[- ]surge advisor(y|ies)\b"), re.compile(r"storm[- ]surge advisory|高潮注意報")),
    "evacuation order": (re.compile(r"\bevacuat(ion|e|ed)\b.{0,40}\b(order|orders|ordered|instruction|instructed|advisory|issued|mandatory)\b|\b(ordered|told) to evacuate\b"),
                         re.compile(r"evacuat|避難指示|避難勧告|高齢者等避難|緊急安全確保")),
    "cancellation or suspension": (re.compile(r"\b(flights?|ferr(y|ies)|ships?|boats?|buses|trains?|services?)\b.{0,50}\b(cancel+ed|suspended|grounded|halted)\b|\b(cancel+ed|suspended)\b.{0,40}\b(flights?|ferr(y|ies)|sailings?|services?)\b"),
                                   re.compile(r"cancel|suspend|欠航|運休|運航を見合わせ|見合わせ")),
    "school closure": (re.compile(r"\bschools?\b.{0,40}\b(closed|closure|cancel+ed|shut)\b|\bclass(es)? (are |have been )?(cancel+ed|suspended)\b"),
                       re.compile(r"school|休校|臨時休業|class suspension")),
    "wind signal": (re.compile(r"\b(tropical cyclone )?wind signal\b|\bsignal no\.?\s*\d"), re.compile(r"wind signal|signal no|signal #")),
}


_FIGURE = re.compile(r"(?<![\w.:])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w:])")
_SMALL = {str(i) for i in range(0, 13)}


def _figures(text: str) -> list[str]:
    """Numbers worth checking: not clock times (12:00), not years, not 0-12 (counting words, 'No. 3')."""
    out = []
    for m in _FIGURE.finditer(text):
        n = m.group(1).replace(",", "")
        if n in _SMALL or (len(n) == 4 and n.startswith(("19", "20")) and "." not in n):
            continue
        out.append(n)
    return out


def _source_numbers(path: Path) -> set[str] | None:
    try:
        rows = read_json(path)["sentences"]
    except (OSError, ValueError, KeyError):
        return None
    pool: set[str] = set()
    for r in rows:
        # permissive on the source side: "16.0N", "100kt", "945hPa" all count
        for m in _POOL_FIGURE.finditer(r["text"]):
            n = m.group(1).replace(",", "")
            pool.add(n)
            if "." in n:
                pool.add(n.rstrip("0").rstrip("."))   # 16.0 -> 16
                pool.add(n)
            else:
                pool.add(n + ".0")                     # 16 -> 16.0
    return pool


_POOL_FIGURE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)")


def _mentions(sentence_low: str, agency: str) -> bool:
    """Does the sentence name this agency (any word of its name of 3+ letters, or its acronym)?"""
    if not agency:
        return False
    parts = [w for w in re.split(r"[^A-Za-z]+", agency.lower()) if len(w) >= 3]
    return any(w in sentence_low for w in parts)


def _content_words(text: str) -> set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z/]{3,}", text)} - _STOP
    return words | set(_NUM.findall(text))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Script harness — owns the write / score / rewrite loop
# ─────────────────────────────────────────────────────────────────────────────


def format_feedback(contradictions: list[str], max_items: int = 8, max_chars: int = 260) -> str:
    """The rewrite feedback: at most ``max_items`` flagged items, one per quoted script sentence, each truncated."""
    seen, lines = set(), []
    for c in contradictions:
        m = re.search(r'"([^"]{12,})"', c)
        key = m.group(1)[:80] if m else c[:80]
        if key in seen:
            continue
        seen.add(key)
        lines.append("- " + (c if len(c) <= max_chars else c[:max_chars - 1] + "…"))
        if len(lines) >= max_items:
            break
    if len(contradictions) > len(lines):
        lines.append(f"- (and {len(contradictions) - len(lines)} more flagged item(s) of the same kind)")
    return "\n".join(lines)


@dataclass
class Attempt:
    index: int
    script: LLMOutput
    score: ScriptScore
    trace: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ScriptHarness:
    """Produces an acceptable script for one scene, iterating until it has one.

    Per attempt: writer.write(scene, context, feedback) -> ScriptScorer.score. Exits on the first
    draft that clears the threshold; after ``max_attempts`` the least-contradictory draft is used
    with a warning. ``accepted`` is false only if no draft could be produced at all.
    """

    def __init__(self, writer: ScriptWriter, max_attempts: int = 3, score_threshold: float = 0.0,
                 scorer: ScriptScorer | None = None, judge: Any = None, attempts_path: Path | None = None) -> None:
        self.writer = writer
        self.max_attempts = max_attempts
        self.score_threshold = score_threshold
        self.scorer = scorer
        self.judge = judge
        self.attempts_path = attempts_path

    def produce(self, scene: Scene, context: RetrievedContext) -> ScriptOutcome:
        scorer = self.scorer or ScriptScorer(threshold=self.score_threshold)
        attempts: list[Attempt] = []
        feedback = ""
        for i in range(1, self.max_attempts + 1):
            try:
                script = self.writer.write(scene, context, feedback)
            except Exception as error:  # noqa: BLE001
                log.error("[qc-b] %s attempt %d: writer failed: %s", scene.title, i, error)
                attempts.append(Attempt(i, LLMOutput(""), ScriptScore(total=float("inf")), error=str(error)))
                self._save(attempts)
                continue
            try:
                score = scorer.score(script, context)
            except Exception as error:  # noqa: BLE001
                # scoring is a safety net, not a gate that may take the stream down
                log.error("[qc-b] %s attempt %d: scoring failed (%s); draft kept unscored", scene.title, i, error)
                score = ScriptScore(total=0.0, passes_threshold=True, contradictions=[f"QC scoring failed: {error}"])
            attempts.append(Attempt(i, script, score, trace=dict(getattr(self.writer, "last_trace", {}))))
            self._save(attempts)
            log.info("[qc-b] %s attempt %d: %d contradiction(s), passes=%s", scene.title, i, len(score.contradictions),
                     score.passes_threshold)
            if score.passes_threshold:
                return ScriptOutcome(script=script, score=score, accepted=True, attempts=i,
                                     warnings=[c for c in score.contradictions if c.startswith("QC scoring failed")])
            feedback = format_feedback(score.contradictions)
        produced = [a for a in attempts if a.error is None]
        if not produced:
            return ScriptOutcome(script=LLMOutput(""), score=ScriptScore(total=float("inf")), accepted=False,
                                 attempts=len(attempts), warnings=[a.error or "" for a in attempts])
        best = min(produced, key=lambda a: a.score.total)
        warn = (f"no draft passed QC after {len(attempts)} attempt(s); using attempt {best.index} "
                f"with {int(best.score.total)} flagged item(s)")
        log.warning("[qc-b] %s: %s", scene.title, warn)
        return ScriptOutcome(script=best.script, score=best.score, accepted=True, attempts=len(attempts), warnings=[warn])

    def _save(self, attempts: list[Attempt]) -> None:
        if not self.attempts_path:
            return
        try:
            write_json(self.attempts_path, [{"index": a.index, "error": a.error, "script": a.script.llm_output,
                                             "score": {"total": a.score.total if a.score.total != float("inf") else None,
                                                       "per_entity": a.score.per_entity, "contradictions": a.score.contradictions,
                                                       "passes_threshold": a.score.passes_threshold},
                                             "trace": a.trace} for a in attempts])
        except OSError as error:
            log.warning("could not save script attempts: %s", error)

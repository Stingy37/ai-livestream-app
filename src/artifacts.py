"""JSON (de)serialisation of the contract dataclasses for the run folder.

The stage workers persist every hand-off (documents, scores, context, script outcome, audio
asset) so a crashed run can resume and so the artifacts can be inspected after the fact.
Datetimes are ISO strings (UTC), paths are strings.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from contracts import (
    AudioAsset,
    LLMOutput,
    RetrievedContext,
    ScoredDocument,
    ScrapedDocument,
    ScriptOutcome,
    ScriptScore,
    Sentence,
)


def _dt(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


def _parse_dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


# ---- documents ---------------------------------------------------------------------------
def document_to_json(d: ScrapedDocument) -> dict[str, Any]:
    out = asdict(d)
    out["published_at"], out["fetched_at"] = _dt(d.published_at), _dt(d.fetched_at)
    return out


def document_from_json(o: dict[str, Any]) -> ScrapedDocument:
    return ScrapedDocument(url=o["url"], title=o.get("title", ""), main_text=o.get("main_text", ""),
                           source_name=o.get("source_name", ""), published_at=_parse_dt(o.get("published_at")),
                           author=o.get("author"), fetched_at=_parse_dt(o.get("fetched_at")), metadata=dict(o.get("metadata") or {}))


def scored_to_json(s: ScoredDocument) -> dict[str, Any]:
    return {"document": document_to_json(s.document), "score": s.score, "score_components": s.score_components,
            "accepted": s.accepted}


def scored_from_json(o: dict[str, Any]) -> ScoredDocument:
    return ScoredDocument(document=document_from_json(o["document"]), score=float(o["score"]),
                          score_components=dict(o.get("score_components") or {}), accepted=bool(o.get("accepted")))


# ---- context -----------------------------------------------------------------------------
def sentence_to_json(s: Sentence) -> dict[str, Any]:
    o = asdict(s)
    o["published_at"] = _dt(s.published_at)
    return o


def sentence_from_json(o: dict[str, Any]) -> Sentence:
    return Sentence(text=o["text"], source_url=o["source_url"], source_name=o["source_name"],
                    published_at=_parse_dt(o.get("published_at")), document_index=int(o["document_index"]),
                    sentence_index=int(o["sentence_index"]))


def context_to_json(c: RetrievedContext) -> dict[str, Any]:
    return {"scene_id": c.scene_id,
            "relevant_sentences": {q: [sentence_to_json(s) for s in ss] for q, ss in c.relevant_sentences.items()}}


def context_from_json(o: dict[str, Any]) -> RetrievedContext:
    return RetrievedContext(scene_id=o["scene_id"],
                            relevant_sentences={q: [sentence_from_json(s) for s in ss]
                                                for q, ss in (o.get("relevant_sentences") or {}).items()})


# ---- scripts -----------------------------------------------------------------------------
def outcome_to_json(o: ScriptOutcome) -> dict[str, Any]:
    total = None if o.score.total == float("inf") else o.score.total
    return {"script": {"llm_output": o.script.llm_output},
            "score": {"total": total, "per_entity": o.score.per_entity, "contradictions": o.score.contradictions,
                      "passes_threshold": o.score.passes_threshold},
            "accepted": o.accepted, "attempts": o.attempts, "warnings": o.warnings}


def outcome_from_json(o: dict[str, Any]) -> ScriptOutcome:
    sc = o.get("score") or {}
    total = sc.get("total")
    return ScriptOutcome(script=LLMOutput(llm_output=(o.get("script") or {}).get("llm_output", "")),
                         score=ScriptScore(total=float("inf") if total is None else float(total),
                                           per_entity=dict(sc.get("per_entity") or {}),
                                           contradictions=list(sc.get("contradictions") or []),
                                           passes_threshold=bool(sc.get("passes_threshold"))),
                         accepted=bool(o.get("accepted")), attempts=int(o.get("attempts", 0)), warnings=list(o.get("warnings") or []))


# ---- audio -------------------------------------------------------------------------------
def asset_to_json(a: AudioAsset) -> dict[str, Any]:
    return {"scene_id": a.scene_id, "path": str(a.path), "duration_seconds": a.duration_seconds,
            "sample_rate": a.sample_rate, "format": a.format, "version": a.version}


def asset_from_json(o: dict[str, Any]) -> AudioAsset:
    return AudioAsset(scene_id=o["scene_id"], path=Path(o["path"]), duration_seconds=float(o["duration_seconds"]),
                      sample_rate=int(o["sample_rate"]), format=o.get("format", "wav"), version=int(o.get("version", 1)))

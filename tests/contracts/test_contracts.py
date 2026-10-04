"""Contract tests: do the hand-off types match the agreed Team Interface Contract?

Deliberately simple. These only compare *declared* datatypes — they never run a
component, so they need no fixtures, API keys, or network.

    1. Every public service method takes and returns exactly the agreed types.
    2. Every contract dataclass has exactly the agreed fields and field types.

If one of these fails on your PR, you changed part of the contract. That needs
agreement from the upstream/downstream teams first; once agreed, update the
expectations below in the same PR.
"""

from __future__ import annotations

import typing
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from audio import AudioGenerator, AudioPlayer
from contracts import (
    AudioAsset,
    LLMOutput,
    RetrievedContext,
    Scene,
    ScoredDocument,
    ScrapedDocument,
    ScriptOutcome,
    ScriptScore,
    Sentence,
)
from qc import ScriptHarness, ScriptScorer, WebsiteScorer
from rag import Retriever
from scraper import WebScraper
from writer import ScriptWriter

# ─────────────────────────────────────────────────────────────────────────────
# 1. Service methods: input and output types
# ─────────────────────────────────────────────────────────────────────────────

SERVICE_METHODS = [
    # (method, {param: type, ..., "return": type})
    (WebScraper.gather, {"scene": Scene, "return": list[ScrapedDocument]}),
    (WebsiteScorer.score_documents, {"documents": list[ScrapedDocument], "return": list[ScoredDocument]}),
    (Retriever.retrieve, {"scene": Scene, "documents": list[ScoredDocument], "return": RetrievedContext}),
    (ScriptWriter.write, {"scene": Scene, "context": RetrievedContext, "feedback": str, "return": LLMOutput}),
    (ScriptHarness.produce, {"scene": Scene, "context": RetrievedContext, "return": ScriptOutcome}),
    (ScriptScorer.score, {"script": LLMOutput, "context": RetrievedContext, "return": ScriptScore}),
    (AudioGenerator.synthesize, {"scene": Scene, "script": LLMOutput, "return": AudioAsset}),
    (AudioPlayer.play, {"asset": AudioAsset, "return": type(None)}),
    (AudioPlayer.stop, {"return": type(None)}),
]


@pytest.mark.parametrize(
    "method, expected", SERVICE_METHODS, ids=[m.__qualname__ for m, _ in SERVICE_METHODS]
)
def test_service_method_types(method, expected):
    assert typing.get_type_hints(method) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 2. Contract dataclasses: fields and field types
# ─────────────────────────────────────────────────────────────────────────────

CONTRACT_FIELDS = [
    (Scene, {
        "id": str,
        "node_key": str,
        "title": str,
        "topic_description": str,
        "system_instructions": str,
        "sources": list[str],
        "language": str,
        "script_model": str,
        "tts_model": str,
        "tts_voice": str,
    }),
    (ScrapedDocument, {
        "url": str,
        "title": str,
        "main_text": str,
        "source_name": str,
        "published_at": datetime | None,
        "author": str | None,
        "fetched_at": datetime | None,
        "metadata": dict[str, Any],
    }),
    (ScoredDocument, {
        "document": ScrapedDocument,
        "score": float,
        "score_components": dict[str, float],
        "accepted": bool,
    }),
    (Sentence, {
        "text": str,
        "source_url": str,
        "source_name": str,
        "published_at": datetime | None,
        "document_index": int,
        "sentence_index": int,
    }),
    (RetrievedContext, {
        "scene_id": str,
        "relevant_sentences": dict[str, list[Sentence]],
    }),
    (LLMOutput, {
        "llm_output": str,
    }),
    (ScriptScore, {
        "total": float,
        "per_entity": dict[str, float],
        "contradictions": list[str],
        "passes_threshold": bool,
    }),
    (ScriptOutcome, {
        "script": LLMOutput,
        "score": ScriptScore,
        "accepted": bool,
        "attempts": int,
        "warnings": list[str],
    }),
    (AudioAsset, {
        "scene_id": str,
        "path": Path,
        "duration_seconds": float,
        "sample_rate": int,
        "format": str,
        "version": int,
    }),
]


@pytest.mark.parametrize(
    "cls, expected", CONTRACT_FIELDS, ids=[c.__name__ for c, _ in CONTRACT_FIELDS]
)
def test_contract_fields(cls, expected):
    assert typing.get_type_hints(cls) == expected

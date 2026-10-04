"""Scripts: script writer → QC harness → Audio."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMOutput:
    """One script draft from the writer.

    Produced by ``writer.ScriptWriter.write``; consumed by the QC harness, and
    carried inside ``ScriptOutcome`` to Audio.
    """

    llm_output: str


@dataclass
class ScriptScore:
    """Result of scoring one candidate script for internal contradictions.

    ``total`` is a contradiction count summed per entity, so **lower is better**
    and zero is a clean script. ``per_entity`` keeps the breakdown so the judge
    and rewrite feedback can point at the specific entity in dispute.
    """

    total: float
    per_entity: dict[str, float] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    passes_threshold: bool = False


@dataclass
class ScriptOutcome:
    """What the QC harness hands back after the write / score / judge loop settles.

    Produced by ``qc.ScriptHarness.produce``; consumed by
    ``audio.AudioGenerator`` (which only reads ``script``).
    """

    script: LLMOutput
    score: ScriptScore
    accepted: bool
    attempts: int
    warnings: list[str] = field(default_factory=list)

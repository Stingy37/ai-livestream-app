"""Includes methods for initializing and traversing the graph representing the livestream.

Takes in user_config.json and builds a graph class from it, acting as a overarching interface for easy interaction with the constructed graph.
Additionally, builds the graph as a class of nodes, representing scenes, with adjacency lists to connected nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class Scene:
    """One playable node of the broadcast, and the unit of work for the pipeline.

    This is the object threaded through every stage: webscraping, clustering,
    retrieval, script generation, and TTS all key off a ``Scene``. It crosses
    process boundaries, so it stays a plain picklable dataclass — no open
    handles, no loaded models, no database connections.

    Division of labour with the config file: everything below ``node_key`` is
    authored by the user and read verbatim out of the json. ``id`` is minted
    here at construction and is what the rest of the pipeline (and the database)
    uses to address this scene's artifacts.
    """

    id: str
    node_key: str

    title: str
    topic_description: str
    system_instructions: str
    do_web_search: bool
    sources: list[str]
    language: str

    # Resolved against the config's top-level ``defaults`` block at build time,
    # so downstream stages never have to know a default existed.
    script_model: str
    tts_model: str
    tts_voice: str


@dataclass
class Cycle:
    """Settings for one non-nested loop in the schedule."""

    id: str
    start_node: str
    end_node: str
    repeat_back_edge: str
    continuation_edge: str
    repetitions: int | None  # None == infinite
    repetitions_until_update: int | None  # None == never regenerate


@dataclass
class ValidationResult:
    """Verdict on whether the graph can proceed to generation.

    Structured rather than boolean so the caller can say *which* element is at
    fault. Purely a report — validation never mutates the graph.
    """

    is_valid: bool
    reasons: list[str] = field(default_factory=list)
    offending_elements: list[str] = field(default_factory=list)


@dataclass
class TraversalStep:
    """One scene handed to the broadcaster, plus the cycle context around it.

    ``update_due`` is the signal main.py watches for: it goes true when the
    containing cycle has completed ``repetitions_until_update`` iterations and
    the scenes in that cycle should be regenerated against fresh sources.
    """

    scene: Scene
    cycle_id: str | None = None
    iteration: int = 0
    update_due: bool = False


class BroadcastGraph:
    """Public interface for the schedule graph.

    Built once from the saved configuration, validated once, and read-only for
    the remainder of the run. Internally: a node map plus adjacency lists.
    """

    def __init__(self, scenes: dict[str, Scene], adjacency: dict[str, list[str]]) -> None:
        raise NotImplementedError

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, path: Path) -> "BroadcastGraph":
        """Build the graph from a saved broadcast configuration json.

        Resolves ``content_library`` references (topic descriptions, system
        instructions, sources) into literal values on each ``Scene``, and folds
        the top-level ``defaults`` into any scene that omitted a model setting.
        Mints a scene ``id`` per scene_card node.

        Should reject a config whose references dangle, whose scene titles
        collide, or whose slugs collide across library sections.
        """
        raise NotImplementedError

    # ── structure ───────────────────────────────────────────────────────────

    def validate(self) -> ValidationResult:
        """Check the graph against the schedule validity rules.

        Read-only and deterministic. Covers: exactly one active start and one
        termination node; start has zero in-edges and one out-edge; termination
        has zero out-edges; a single linear active path with no branching; no
        nested cycles; every finite cycle fully specified and continuing toward
        termination or another linear cycle.

        Scene *card* validity — whether a card's required fields are filled — is
        a separate concern and is not checked here.
        """
        raise NotImplementedError

    def neighbors(self, node_key: str) -> list[str]:
        """Adjacency lookup: node keys reachable in one edge from ``node_key``."""
        raise NotImplementedError

    def active_scenes(self) -> list[Scene]:
        """Scenes on the start → termination path, in schedule order.

        Excludes disconnected scene nodes, which are legal in the editor but are
        never generated or played. This is what main.py generates against.
        """
        raise NotImplementedError

    def scenes_in_cycle(self, cycle_id: str) -> list[Scene]:
        """Scenes contained in one cycle — the regeneration unit for that loop."""
        raise NotImplementedError

    # ── traversal ───────────────────────────────────────────────────────────

    def traversal(self) -> Iterator[TraversalStep]:
        """Yield scenes in playback order, expanding cycles as it goes.

        Lazy on purpose: an infinite cycle is an infinite iterator, and the
        consumer decides when to stop. Cycle bookkeeping — iteration counts and
        raising ``update_due`` at the configured interval — lives here rather
        than in main.py, so the broadcaster only has to play what it is given.
        """
        raise NotImplementedError

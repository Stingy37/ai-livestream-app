"""The broadcast graph: builds ``Scene``s from the saved config and drives traversal.

Reads a saved configuration json (see saved_configs/example.json): ``content_library`` references
are resolved into literal values on each ``Scene``, ``defaults`` are folded in, and each scene_card
node gets a stable id (``sc-<node_key>``) that labels everything it produces (run folder, package
files, website playlist), so a regenerated scene replaces the previous version under the same id.

Traversal walks start -> ... -> termination. A ``cycles`` entry repeats the scenes between its
start_node and end_node ``repetitions`` times (None = forever) and raises ``update_due`` on the
end node every ``repetitions_until_update`` iterations, which is the harness's cue to regenerate
that cycle's scenes against fresh sources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from contracts import Scene

SCENE_FIELDS_FROM_DEFAULTS = ("language", "script_model", "tts_model", "tts_voice")


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


@dataclass
class SceneOptions:
    """Per-scene settings that are not part of the ``Scene`` contract."""

    do_web_search: bool = False


class ConfigError(ValueError):
    """The saved configuration cannot be turned into a graph."""


class BroadcastGraph:
    """Public interface for the schedule graph.

    Built once from the saved configuration, validated once, and read-only for
    the remainder of the run. Internally: a node map plus adjacency lists.
    """

    def __init__(self, scenes: dict[str, Scene], adjacency: dict[str, list[str]], *,
                 node_types: dict[str, str] | None = None, edges: list[dict[str, Any]] | None = None,
                 cycles: list[Cycle] | None = None, options: dict[str, SceneOptions] | None = None,
                 config_name: str = "", storm: dict[str, str] | None = None) -> None:
        self.scenes = dict(scenes)                 # node_key -> Scene
        self.adjacency = {k: list(v) for k, v in adjacency.items()}
        self.node_types = dict(node_types or {k: "scene_card" for k in scenes})
        self.edges = list(edges or [])
        self.cycles = list(cycles or [])
        self.options = dict(options or {})         # node_key -> SceneOptions
        self.config_name = config_name
        self.storm = dict(storm or {})
        self._scene_by_id = {s.id: s for s in self.scenes.values()}

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, path: Path) -> "BroadcastGraph":
        """Build the graph from a saved broadcast configuration json."""
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        library = cfg.get("content_library", {})
        defaults = cfg.get("defaults", {})
        topics = library.get("topic_descriptions", {})
        instructions = library.get("system_instructions", {})
        sources = library.get("sources", {})
        _check_slug_collisions(topics, instructions, sources)

        graph = cfg.get("graph", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        scenes: dict[str, Scene] = {}
        options: dict[str, SceneOptions] = {}
        node_types: dict[str, str] = {}
        titles: set[str] = set()
        for node in nodes:
            key, ntype = node["key"], node["type"]
            node_types[key] = ntype
            if ntype != "scene_card":
                continue
            sc = node.get("scene") or {}
            topic_ref = sc.get("topic_description", "")
            instr_ref = sc.get("final_script_system_instructions", sc.get("system_instructions", ""))
            if topic_ref not in topics:
                raise ConfigError(f"node {key!r}: topic_description {topic_ref!r} is not in content_library")
            if instr_ref not in instructions:
                raise ConfigError(f"node {key!r}: system_instructions {instr_ref!r} is not in content_library")
            urls = []
            for ref in sc.get("sources", []):
                if ref not in sources:
                    raise ConfigError(f"node {key!r}: source {ref!r} is not in content_library")
                urls.append(sources[ref]["url"])
            title = sc.get("title", key)
            if title in titles:
                raise ConfigError(f"scene title {title!r} is used by more than one node")
            titles.add(title)
            gen = sc.get("generation") or {}
            resolved = {f: gen.get(f, sc.get(f, defaults.get(f, ""))) for f in SCENE_FIELDS_FROM_DEFAULTS}
            scenes[key] = Scene(
                id=f"sc-{key}",
                node_key=key,
                title=title,
                topic_description=topics[topic_ref]["content"],
                system_instructions=instructions[instr_ref]["content"],
                sources=urls,
                language=resolved["language"] or "en",
                script_model=resolved["script_model"],
                tts_model=resolved["tts_model"],
                tts_voice=resolved["tts_voice"],
            )
            options[key] = SceneOptions(do_web_search=bool(sc.get("do_web_search", False)))

        adjacency: dict[str, list[str]] = {n["key"]: [] for n in nodes}
        for e in edges:
            adjacency.setdefault(e["source"], []).append(e["target"])
        cycles = [Cycle(id=c["id"], start_node=c["start_node"], end_node=c["end_node"],
                        repeat_back_edge=c["repeat_back_edge"], continuation_edge=c["continuation_edge"],
                        repetitions=c.get("repetitions"), repetitions_until_update=c.get("repetitions_until_update"))
                  for c in graph.get("cycles", [])]
        return cls(scenes, adjacency, node_types=node_types, edges=edges, cycles=cycles, options=options,
                   config_name=cfg.get("config", {}).get("name", ""), storm=cfg.get("config", {}).get("storm", {}))

    # ── structure ───────────────────────────────────────────────────────────

    def validate(self) -> ValidationResult:
        """Check the graph against the schedule validity rules (read-only, deterministic)."""
        reasons, bad = [], []
        starts = [k for k, t in self.node_types.items() if t == "start"]
        ends = [k for k, t in self.node_types.items() if t == "termination"]
        if len(starts) != 1:
            reasons.append(f"expected exactly one start node, found {len(starts)}")
            bad += starts
        if len(ends) != 1:
            reasons.append(f"expected exactly one termination node, found {len(ends)}")
            bad += ends
        in_edges = {k: 0 for k in self.node_types}
        for e in self.edges:
            in_edges[e["target"]] = in_edges.get(e["target"], 0) + 1
        for s in starts:
            if in_edges.get(s, 0) != 0 or len(self.adjacency.get(s, [])) != 1:
                reasons.append(f"start node {s!r} must have zero in-edges and one out-edge")
                bad.append(s)
        for t in ends:
            if self.adjacency.get(t):
                reasons.append(f"termination node {t!r} must have zero out-edges")
                bad.append(t)
        by_id = {e["id"]: e for e in self.edges}
        for c in self.cycles:
            for ref in (c.repeat_back_edge, c.continuation_edge):
                if ref not in by_id:
                    reasons.append(f"cycle {c.id}: edge {ref!r} does not exist")
                    bad.append(c.id)
            rb = by_id.get(c.repeat_back_edge)
            if rb and not (rb["source"] == c.end_node and rb["target"] == c.start_node):
                reasons.append(f"cycle {c.id}: repeat_back edge must go from end_node to start_node")
                bad.append(c.id)
            if c.repetitions is not None and c.repetitions < 1:
                reasons.append(f"cycle {c.id}: repetitions must be >= 1 or null")
                bad.append(c.id)
        # linear forward path: every node on it has exactly one forward edge
        if starts and ends:
            path = self._forward_path(starts[0])
            if not path or path[-1] != ends[0]:
                reasons.append("the forward path from start does not reach the termination node")
                bad.append(starts[0])
            for k in path:
                fwd = [e for e in self.edges if e["source"] == k and e.get("type", "normal") != "repeat_back"]
                if self.node_types.get(k) != "termination" and len(fwd) != 1:
                    reasons.append(f"node {k!r} must have exactly one forward edge (has {len(fwd)})")
                    bad.append(k)
        # no nested cycles: cycle spans must not overlap
        spans = []
        for c in self.cycles:
            path = self._forward_path(starts[0]) if starts else []
            try:
                a, b = path.index(c.start_node), path.index(c.end_node)
            except ValueError:
                reasons.append(f"cycle {c.id}: start/end node not on the active path")
                bad.append(c.id)
                continue
            spans.append((a, b, c.id))
        spans.sort()
        for (a1, b1, i1), (a2, b2, i2) in zip(spans, spans[1:]):
            if a2 <= b1:
                reasons.append(f"cycles {i1} and {i2} overlap (nested cycles are not allowed)")
                bad += [i1, i2]
        return ValidationResult(is_valid=not reasons, reasons=reasons, offending_elements=sorted(set(bad)))

    def neighbors(self, node_key: str) -> list[str]:
        """Adjacency lookup: node keys reachable in one edge from ``node_key``."""
        return list(self.adjacency.get(node_key, []))

    def active_scenes(self) -> list[Scene]:
        """Scenes on the start -> termination path, in schedule order."""
        return [self.scenes[k] for k in self._forward_path(self._start_key()) if k in self.scenes]

    def scenes_in_cycle(self, cycle_id: str) -> list[Scene]:
        """Scenes contained in one cycle — the regeneration unit for that loop."""
        c = self._cycle(cycle_id)
        path = self._forward_path(self._start_key())
        a, b = path.index(c.start_node), path.index(c.end_node)
        return [self.scenes[k] for k in path[a:b + 1] if k in self.scenes]

    def scene_by_id(self, scene_id: str) -> Scene:
        return self._scene_by_id[scene_id]

    def scene_options(self, scene: Scene | str) -> SceneOptions:
        key = scene if isinstance(scene, str) else scene.node_key
        return self.options.get(key, SceneOptions())

    def cycle_of(self, node_key: str) -> Cycle | None:
        path = self._forward_path(self._start_key())
        for c in self.cycles:
            a, b = path.index(c.start_node), path.index(c.end_node)
            if a <= path.index(node_key) <= b:
                return c
        return None

    # ── traversal ───────────────────────────────────────────────────────────

    def traversal(self) -> Iterator[TraversalStep]:
        """Yield scenes in playback order, expanding cycles as it goes (lazy; may be infinite)."""
        path = self._forward_path(self._start_key())
        i = 0
        while i < len(path):
            key = path[i]
            cycle = next((c for c in self.cycles if c.start_node == key), None)
            if cycle is None:
                if key in self.scenes:
                    yield TraversalStep(scene=self.scenes[key])
                i += 1
                continue
            a, b = path.index(cycle.start_node), path.index(cycle.end_node)
            body = [k for k in path[a:b + 1] if k in self.scenes]
            iteration = 0
            while cycle.repetitions is None or iteration < cycle.repetitions:
                iteration += 1
                for j, k in enumerate(body):
                    last = j == len(body) - 1
                    due = bool(last and cycle.repetitions_until_update and iteration % cycle.repetitions_until_update == 0)
                    yield TraversalStep(scene=self.scenes[k], cycle_id=cycle.id, iteration=iteration, update_due=due)
            i = b + 1

    def playlist(self) -> list[str]:
        """Scene ids of one full pass (an infinite cycle counts once); what the website loops over."""
        out: list[str] = []
        path = self._forward_path(self._start_key())
        i = 0
        while i < len(path):
            key = path[i]
            cycle = next((c for c in self.cycles if c.start_node == key), None)
            if cycle is None:
                if key in self.scenes:
                    out.append(self.scenes[key].id)
                i += 1
                continue
            a, b = path.index(cycle.start_node), path.index(cycle.end_node)
            body = [self.scenes[k].id for k in path[a:b + 1] if k in self.scenes]
            out.extend(body * (cycle.repetitions or 1))
            i = b + 1
        return out

    # ── helpers ─────────────────────────────────────────────────────────────

    def _start_key(self) -> str:
        for k, t in self.node_types.items():
            if t == "start":
                return k
        raise ConfigError("no start node")

    def _cycle(self, cycle_id: str) -> Cycle:
        for c in self.cycles:
            if c.id == cycle_id:
                return c
        raise KeyError(cycle_id)

    def _forward_path(self, start: str) -> list[str]:
        """Node keys from ``start`` following non-repeat_back edges until no edge is left."""
        path, seen, key = [start], {start}, start
        while True:
            fwd = [e["target"] for e in self.edges if e["source"] == key and e.get("type", "normal") != "repeat_back"]
            if not fwd or fwd[0] in seen:
                return path
            key = fwd[0]
            seen.add(key)
            path.append(key)


def _check_slug_collisions(*sections: dict[str, Any]) -> None:
    seen: dict[str, int] = {}
    for i, section in enumerate(sections):
        for slug in section:
            if slug in seen and seen[slug] != i:
                raise ConfigError(f"slug {slug!r} is used in more than one content_library section")
            seen[slug] = i

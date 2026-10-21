"""Backend pipeline entrypoint and broadcast harness for the AI Livestream Hub (Typhoon Champi desk).

This module owns *sequencing only*. Every unit of real work lives in a team package under
``src/`` and is reached through that package's public interface class (the Team Interface
Contract, enforced by ``src/contracts`` and ``tests/contracts``).

Pipeline stages, one per team boundary:

    1. sources ..... scraper.WebScraper (LangGraph agent) + qc.WebsiteScorer (Part A)  -> list[ScoredDocument]
    2. context ..... rag.Retriever (sentence index + up-front retrieval)               -> RetrievedContext
    3. script ...... qc.ScriptHarness (writer.ScriptWriter dynamic RAG + qc Part B)    -> ScriptOutcome
    4. audio ....... audio.AudioGenerator (Kokoro)                                     -> AudioAsset
    5. broadcast ... broadcast.PackageBuilder + broadcast.Publisher (S3 via EC2) and the on-air
                     clock (graph.BroadcastGraph traversal) that triggers cycle regeneration

CONCURRENCY MODEL: processes within modules, threads within processes. One process per scene
per stage; a stage is a barrier. Every hand-off is a plain picklable dataclass and is also
written to the run folder (see config_env.RunLayout) so a crashed run resumes where it stopped.

FAILURE POLICY: a scene that fails a stage is retried; if it still fails it is dropped from
*this* generation with an error logged, and the broadcast carries on with the scenes that
succeeded (during a regeneration the previous version of a failed scene stays on air). Only a
generation with zero usable scenes is fatal, and then scripts/run_livestream.sh restarts the
harness with the same RUN_ID so it resumes.

All knobs come from environment variables (config_env.Settings); scripts/run_livestream.sh sets them.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import multiprocessing as mp
import os
import shutil
import signal
import sys
import threading
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from config_env import REPO_ROOT, RunLayout, Settings, read_json, write_json

log = logging.getLogger("livestream")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SceneResult:
    """Outcome of one scene's work within one stage (warning = recoverable, error = scene dropped)."""

    scene_id: str
    ok: bool
    value: Any = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunContext:
    """Everything a worker process needs; inert and picklable."""

    settings: Settings
    generation: int = 1                     # 1 = initial build, +1 per cycle regeneration
    reason: str = "initial"
    web_search_scenes: str = ""             # comma-separated node keys with do_web_search on


@dataclass
class SceneBundle:
    """Everything the package needs for one scene, kept in memory for the broadcast loop."""

    scene_id: str
    node_key: str
    title: str
    version: int
    outcome_json: dict[str, Any]
    audio_json: dict[str, Any]
    sources: list[dict[str, Any]] = field(default_factory=list)
    qc: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    @property
    def duration(self) -> float:
        return float(self.audio_json.get("duration_seconds", 0.0))

    @property
    def audio_path(self) -> Path:
        return Path(self.audio_json["path"])


class PipelineError(RuntimeError):
    """Unrecoverable failure of a whole generation."""


# ─────────────────────────────────────────────────────────────────────────────
# Parallel stage driver
# ─────────────────────────────────────────────────────────────────────────────


def _init_worker(log_level: str, env: dict[str, str]) -> None:
    os.environ.update(env)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    logging.basicConfig(level=log_level.upper(), format="%(asctime)s  %(levelname)-7s  [pid %(process)d] %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "urllib3", "faiss.loader", "trafilatura", "htmldate", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_scene_stage(stage_name: str, worker: Callable[..., SceneResult], scenes: Sequence[Any], ctx: RunContext,
                    upstream: dict[str, Any] | None = None, retries: int = 1) -> dict[str, SceneResult]:
    """Run ``worker`` once per scene, one process each; retry failed scenes; never raise per scene."""
    if not scenes:
        return {}
    results: dict[str, SceneResult] = {}
    todo = list(scenes)
    env = {k: v for k, v in os.environ.items() if k in _WORKER_ENV_KEYS or k.startswith(("LUMEN_", "SCRAPE_", "QC_", "EC2_", "REWRITE_", "DESK_", "MOSS_"))}
    for attempt in range(retries + 1):
        if not todo:
            break
        log.info("[%s] starting %d scene process(es)%s", stage_name, len(todo), f" (retry {attempt})" if attempt else "")
        with ProcessPoolExecutor(max_workers=min(ctx.settings.max_workers, len(todo)), mp_context=mp.get_context("spawn"),
                                 initializer=_init_worker, initargs=(ctx.settings.log_level, env)) as pool:
            futures: dict[Future[SceneResult], Any] = {
                pool.submit(worker, scene, ctx, (upstream or {}).get(scene.id)): scene for scene in todo}
            for future in as_completed(futures):
                scene = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # a worker died outright
                    log.exception("[%s] scene %r crashed", stage_name, scene.title)
                    result = SceneResult(scene.id, ok=False, error=f"{type(exc).__name__}: {exc}")
                results[scene.id] = result
        todo = [s for s in todo if not results[s.id].ok]
    _log_stage_summary(stage_name, scenes, results)
    return results


_WORKER_ENV_KEYS = {"RUN_ID", "RUN_ROOT", "CONFIG_PATH", "LOCAL_LLM_URL", "LOCAL_LLM_MODEL", "LORA_NAME", "SEARXNG_URL",
                    "E5_DIR", "E5_DEVICE", "KOKORO_DIR", "TTS_DEVICE", "NLI_MODEL_DIR", "NLI_DEVICE", "MAX_TOKENS",
                    "THINK_FRACTION", "MAX_OBS_TOKENS", "CONTEXT_TOPK", "RETRIEVAL_TOP_K", "GEN_TEMPERATURE", "GEN_TOP_P",
                    "GEN_TOP_K", "SCRIPT_MAX_ATTEMPTS", "SCRIPT_SCORE_THRESHOLD", "STALE_HOURS", "REACT_MAX_ROUNDS",
                    "LOCAL_LLM_MAX_MODEL_LEN", "LOCAL_LLM_MODEL_PATH", "TTS_DEFAULT_VOICE", "LOG_LEVEL", "MIN_SENTENCE_CHARS",
                    "HF_HUB_OFFLINE", "CUDA_VISIBLE_DEVICES", "PYTHONPATH", "PATH", "HOME", "SPEECH_WPS", "GPU_TIMESHARE"}


def _log_stage_summary(stage_name: str, scenes: Sequence[Any], results: dict[str, SceneResult]) -> None:
    by_id = {scene.id: scene for scene in scenes}
    for scene_id, result in results.items():
        title = by_id[scene_id].title
        for warning in result.warnings:
            log.warning("[%s] %s: %s", stage_name, title, warning)
        if not result.ok:
            log.error("[%s] %s: FAILED: %s", stage_name, title, result.error)


# ─────────────────────────────────────────────────────────────────────────────
# Stage workers (module-level so they survive pickling under "spawn")
# ─────────────────────────────────────────────────────────────────────────────


def _state(layout: RunLayout, scene_id: str) -> dict[str, Any]:
    p = layout.scene_dir(scene_id) / "stage_state.json"
    return read_json(p) if p.is_file() else {}


def _mark(layout: RunLayout, scene_id: str, stage: str, generation: int) -> None:
    st = _state(layout, scene_id)
    st[stage] = generation
    write_json(layout.scene_dir(scene_id) / "stage_state.json", st)


def _reusable(ctx: RunContext, layout: RunLayout, scene_id: str, stage: str, artifact: Path) -> bool:
    return ctx.settings.resume and artifact.is_file() and _state(layout, scene_id).get(stage) == ctx.generation


def sources_stage(scene, ctx: RunContext, _upstream: None) -> SceneResult:
    """Stage 1: agentic scraping + QC Part A. ``value`` -> accepted list[ScoredDocument]."""
    from artifacts import document_to_json, scored_from_json, scored_to_json
    from qc import WebsiteScorer
    from scraper import WebScraper

    layout = ctx.settings.layout()
    scored_path = layout.scored_json(scene.id)
    if _reusable(ctx, layout, scene.id, "sources", scored_path):
        scored = [scored_from_json(o) for o in read_json(scored_path)]
        log.info("[sources] %s: reusing %d scored documents from the run folder", scene.title, len(scored))
        return SceneResult(scene.id, ok=True, value=[s for s in scored if s.accepted] or scored)

    os.environ["SCRAPE_WEB_SEARCH_SCENES"] = ctx.web_search_scenes
    scraper = WebScraper(max_threads=ctx.settings.scrape_max_threads)
    documents = scraper.gather(scene)
    report = getattr(scraper, "last_report", None) or {}
    write_json(layout.scrape_report(scene.id), report)
    write_json(layout.sources_json(scene.id), [document_to_json(d) for d in documents])
    if not documents:
        return SceneResult(scene.id, ok=False, error="no sources could be retrieved")

    scorer = WebsiteScorer(scene_dir=layout.scene_dir(scene.id))
    try:
        scored = scorer.score_documents(documents)
    except Exception as error:  # noqa: BLE001 - QC must not take the stream down
        log.exception("[sources] %s: QC Part A failed; keeping every document unscored", scene.title)
        from contracts import ScoredDocument

        scored = [ScoredDocument(document=d, score=0.5, score_components={"agreement": 0.5}, accepted=True) for d in documents]
        scorer.last_result = {"error": str(error)}
    write_json(layout.qc_part_a(scene.id), scorer.last_result)
    write_json(scored_path, [scored_to_json(s) for s in scored])
    _mark(layout, scene.id, "sources", ctx.generation)
    accepted = [s for s in scored if s.accepted]
    warnings = [f"dropped {s.document.url} (agreement {s.score_components.get('agreement', 0):.2f} below threshold)"
                for s in scored if not s.accepted]
    if not accepted:
        return SceneResult(scene.id, ok=False, warnings=warnings, error="every source failed website quality control")
    return SceneResult(scene.id, ok=True, value=accepted, warnings=warnings)


def context_stage(scene, ctx: RunContext, documents) -> SceneResult:
    """Stage 2: sentence index + up-front retrieval (RAG). ``value`` -> RetrievedContext."""
    from artifacts import context_from_json, context_to_json
    from rag import Retriever

    layout = ctx.settings.layout()
    path = layout.context_json(scene.id)
    if _reusable(ctx, layout, scene.id, "context", path) and (layout.index_dir(scene.id) / "vectors.npy").is_file():
        context = context_from_json(read_json(path))
        log.info("[context] %s: reusing the saved index and context", scene.title)
        return SceneResult(scene.id, ok=True, value=context)
    retriever = Retriever(top_k=ctx.settings.retrieval_top_k)
    context = retriever.retrieve(scene, documents)
    write_json(path, context_to_json(context))
    _mark(layout, scene.id, "context", ctx.generation)
    if not context.is_populated():
        return SceneResult(scene.id, ok=False, error="retrieval returned no sentences")
    warnings = [f"no source answered: {q[:80]}" for q in context.unanswered_queries()]
    return SceneResult(scene.id, ok=True, value=context, warnings=warnings)


def script_stage(scene, ctx: RunContext, context) -> SceneResult:
    """Stage 3: dynamic-RAG writing + QC Part B loop. ``value`` -> ScriptOutcome."""
    from artifacts import outcome_from_json, outcome_to_json
    from qc import ScriptHarness, ScriptScorer
    from writer import ScriptWriter

    layout = ctx.settings.layout()
    path = layout.script_json(scene.id)
    if _reusable(ctx, layout, scene.id, "script", path):
        outcome = outcome_from_json(read_json(path))
        if outcome.accepted and outcome.script.llm_output.strip():
            log.info("[script] %s: reusing the saved script", scene.title)
            return SceneResult(scene.id, ok=True, value=outcome, warnings=outcome.warnings)
    s = ctx.settings
    harness = ScriptHarness(writer=ScriptWriter(), max_attempts=s.script_max_attempts, score_threshold=s.script_score_threshold,
                            scorer=ScriptScorer(threshold=s.script_score_threshold, scene_dir=layout.scene_dir(scene.id)),
                            attempts_path=layout.script_attempts(scene.id))
    outcome = harness.produce(scene=scene, context=context)
    from qc.quality_control import ALERT_PREFIX
    bad = [c for c in (outcome.score.contradictions if outcome.score else []) if c.startswith(ALERT_PREFIX)]
    if bad:
        write_json(layout.scene_dir(scene.id) / "script_rejected.json", {"alerts": bad, "script": outcome.script.llm_output})
        return SceneResult(scene.id, ok=False, warnings=outcome.warnings,
                           error=f"best script still states {len(bad)} unsupported alert(s): {bad[0][:160]}")
    write_json(path, outcome_to_json(outcome))
    _mark(layout, scene.id, "script", ctx.generation)
    if not outcome.accepted or not outcome.script.llm_output.strip():
        return SceneResult(scene.id, ok=False, warnings=outcome.warnings, error="no candidate script could be produced")
    return SceneResult(scene.id, ok=True, value=outcome, warnings=outcome.warnings)


def rewrite_stage(scene, ctx: RunContext, outcome) -> SceneResult:
    """Stage 3b: last-stage rewrite of the QC-checked script for narrative and analysis (writer.rewriter).

    For an English scene this never fails: when the rewrite model is down or every rewrite breaks a guard,
    the QC-checked draft goes on to audio unchanged. A non-English scene with no checked translation fails
    (retried, then dropped from the cycle): the English draft must never be read by a non-English voice.
    ``value`` -> ScriptOutcome.
    """
    from artifacts import outcome_from_json, outcome_to_json
    from writer.rewriter import ScriptRewriter

    layout = ctx.settings.layout()
    path = layout.scene_dir(scene.id) / "rewrite.json"
    if os.environ.get("REWRITE_ENABLED", "1") != "1":
        return SceneResult(scene.id, ok=True, value=outcome)
    if _reusable(ctx, layout, scene.id, "rewrite", path):
        saved = read_json(path)
        log.info("[rewrite] %s: reusing the saved %s", scene.title, "rewrite" if saved.get("used_rewrite") else "draft")
        return SceneResult(scene.id, ok=True, value=outcome_from_json(saved["outcome"]))
    result = ScriptRewriter().rewrite(scene, outcome)
    if not result.used_rewrite and (scene.language or "en").lower().split("-")[0] != "en":
        write_json(layout.scene_dir(scene.id) / "rewrite_failed.json", {"reason": result.reason, "attempts": result.attempts})
        return SceneResult(scene.id, ok=False, error=f"no checked {scene.language} script: {result.reason}")
    write_json(path, {"used_rewrite": result.used_rewrite, "reason": result.reason, "model": ScriptRewriter().model,
                      "draft": outcome.script.llm_output, "attempts": result.attempts,
                      "outcome": outcome_to_json(result.outcome)})
    _mark(layout, scene.id, "rewrite", ctx.generation)
    warnings = [] if result.used_rewrite else [f"rewrite skipped: {result.reason}"]
    return SceneResult(scene.id, ok=True, value=result.outcome, warnings=warnings)


def audio_stage(scene, ctx: RunContext, outcome) -> SceneResult:
    """Stage 4: TTS. ``value`` -> SceneBundle (json-friendly, what the package needs)."""
    from artifacts import asset_from_json, asset_to_json, outcome_to_json
    from audio import AudioGenerator

    layout = ctx.settings.layout()
    path = layout.audio_json(scene.id)
    if _reusable(ctx, layout, scene.id, "audio", path) and layout.audio_wav(scene.id).is_file():
        asset = asset_from_json(read_json(path))
        log.info("[audio] %s: reusing the saved clip (%.1fs)", scene.title, asset.duration_seconds)
    else:
        generator = AudioGenerator(out_dir=layout.scene_dir(scene.id))
        asset = generator.synthesize(scene=scene, script=outcome.script)
        _mark(layout, scene.id, "audio", ctx.generation)
    bundle = SceneBundle(scene_id=scene.id, node_key=scene.node_key, title=scene.title, version=ctx.generation,
                         outcome_json=outcome_to_json(outcome), audio_json=asset_to_json(asset),
                         sources=_source_summaries(layout, scene.id), qc=_qc_summary(layout, scene.id, outcome),
                         generated_at=datetime.now(timezone.utc).isoformat())
    write_json(layout.scene_dir(scene.id) / "bundle.json", dataclasses.asdict(bundle))
    return SceneResult(scene.id, ok=True, value=bundle)


def _source_summaries(layout: RunLayout, scene_id: str) -> list[dict[str, Any]]:
    p = layout.scored_json(scene_id)
    if not p.is_file():
        return []
    out = []
    for o in read_json(p):
        d = o["document"]
        out.append({"url": d["url"], "source_name": d.get("source_name", ""), "title": d.get("title", ""),
                    "published_at": d.get("published_at"), "accepted": o.get("accepted", True),
                    "agreement": (o.get("score_components") or {}).get("agreement")})
    return out


def _qc_summary(layout: RunLayout, scene_id: str, outcome) -> dict[str, Any]:
    a = read_json(layout.qc_part_a(scene_id)) if layout.qc_part_a(scene_id).is_file() else {}
    return {"attempts": outcome.attempts, "accepted": outcome.accepted,
            "score_total": None if outcome.score.total == float("inf") else outcome.score.total,
            "contradictions": outcome.score.contradictions[:12], "warnings": outcome.warnings,
            "part_a": {"pairs_compared": a.get("pairs_compared"), "flagged_pairs": len(a.get("flagged_pairs", [])),
                       "removed": a.get("removed", []), "effective_threshold": a.get("effective_threshold")}}


# ─────────────────────────────────────────────────────────────────────────────
# Generation — stages 1 through 4
# ─────────────────────────────────────────────────────────────────────────────

STAGES: list[tuple[str, Callable[..., SceneResult]]] = [
    ("sources", sources_stage), ("context", context_stage), ("script", script_stage), ("rewrite", rewrite_stage),
    ("audio", audio_stage)]


def generate_scenes(scenes: Sequence[Any], ctx: RunContext, stop: threading.Event | None = None) -> dict[str, SceneBundle]:
    """Run stages 1-4 over ``scenes``; returns a bundle per scene that made it through every stage."""
    t0 = time.time()
    alive = list(scenes)
    upstream: dict[str, Any] | None = None
    dropped: dict[str, str] = {}
    for stage_name, worker in STAGES:
        if stop is not None and stop.is_set():
            raise PipelineError("stopped")
        timeshare = (stage_name == "audio" and os.environ.get("GPU_TIMESHARE", "0") == "1"
                     and any((s.tts_model or "").lower().startswith("moss") for s in alive))
        if timeshare:
            # the full MOSS model needs the whole GPU slice: vLLM sleeps while this stage runs (models/gpu.py)
            from models import gpu

            with gpu.tts_phase():
                results = run_scene_stage(stage_name, worker, alive, ctx, upstream)
        else:
            results = run_scene_stage(stage_name, worker, alive, ctx, upstream)
        for s in alive:
            r = results.get(s.id)
            if r is None or not r.ok:
                dropped[s.id] = (r.error if r else "no result") or "unknown"
        alive = [s for s in alive if results.get(s.id) and results[s.id].ok]
        upstream = {s.id: results[s.id].value for s in alive}
        log.info("[%s] complete: %d ok, %d dropped (%.0fs since generation start)", stage_name, len(alive), len(dropped), time.time() - t0)
        if not alive:
            raise PipelineError(f"{stage_name} failed for every scene: {dropped}")
    bundles = {sid: b for sid, b in (upstream or {}).items()}
    for sid, why in dropped.items():
        log.error("scene %s dropped from generation %d: %s", sid, ctx.generation, why)
    return bundles


# ─────────────────────────────────────────────────────────────────────────────
# Packaging + publishing (stage 5a)
# ─────────────────────────────────────────────────────────────────────────────


class Broadcaster:
    """Builds packages from the current bundles and pushes them to the website via EC2/S3."""

    def __init__(self, graph, settings: Settings, publish: bool) -> None:
        from broadcast import PackageBuilder

        self.graph = graph
        self.settings = settings
        self.publish_enabled = publish
        self.builder = PackageBuilder(settings.layout().packages_dir, graph.config_name, settings.run_id,
                                      storm=graph.storm)
        self.publisher = None
        self.current_package: str | None = None
        self.published: list[str] = []
        self.failed_publishes = 0

    def _publisher(self):
        if self.publisher is None:
            from broadcast.publisher import Publisher

            self.publisher = Publisher()
        return self.publisher

    def push(self, bundles: dict[str, SceneBundle], reason: str) -> str | None:
        """Build a package from the bundles and publish it. Returns the package id (or None if nothing to send)."""
        from broadcast.package import SceneEntry

        playlist = [sid for sid in self.graph.playlist() if sid in bundles]
        if not playlist:
            log.error("no scene has audio; nothing to publish")
            return None
        entries = []
        for sid in dict.fromkeys(playlist):
            b = bundles[sid]
            entries.append(SceneEntry(scene_id=sid, node_key=b.node_key, title=b.title, version=b.version,
                                      script_text=b.outcome_json["script"]["llm_output"], audio_src=b.audio_path,
                                      headline=_headline(b), sources=b.sources, qc=b.qc, generated_at=b.generated_at))
        pdir = self.builder.build(entries, playlist, reason=reason, replaces=self.current_package)
        pid = pdir.name
        log.info("package %s built (%d scenes, playlist %d items, reason: %s)", pid, len(entries), len(playlist), reason)
        if self.publish_enabled:
            try:
                reply = self._publisher().upload_package(pdir)
                self.current_package = pid
                self.published.append(pid)
                self.failed_publishes = 0
                log.info("package %s published and activated on EC2 (retired: %s)", pid, reply.get("retired") or [])
                self._prune_local(reply.get("retired") or [])
            except Exception as error:  # noqa: BLE001
                self.failed_publishes += 1
                log.error("publishing %s failed (%d in a row): %s", pid, self.failed_publishes, error)
                return None
        else:
            self.current_package = pid
        return pid

    def _prune_local(self, retired: list[str]) -> None:
        pk = self.settings.layout().packages_dir
        keep = set(self.published[-self.settings.keep_packages:])
        for d in sorted(p for p in pk.iterdir() if p.is_dir()):
            if d.name in retired or (d.name not in keep and d.name != self.current_package and d.name in self.published):
                shutil.rmtree(d, ignore_errors=True)
                log.info("removed local package %s", d.name)


def _headline(b: SceneBundle) -> dict[str, str]:
    text = b.outcome_json["script"]["llm_output"].strip()
    first = text.split(". ")[0].strip() if text else b.title
    if len(first) > 110:
        first = first[:107].rsplit(" ", 1)[0] + "…"
    agencies = sorted({s.get("source_name", "") for s in b.sources if s.get("accepted", True) and s.get("source_name")})
    sub = ("Sources: " + ", ".join(agencies)) if agencies else ""
    return {"main": first, "sub": sub, "tag": b.title.upper()}


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast loop (stage 5b): on-air clock + cycle regeneration
# ─────────────────────────────────────────────────────────────────────────────


def broadcast(graph, ctx: RunContext, bundles: dict[str, SceneBundle], caster: Broadcaster, *, clock_speed: float,
              loop: bool, deadline: float, stop: threading.Event, active_ids: set[str] | None = None) -> None:
    """Walk the graph at the real pace of the clips; regenerate cycles when they come due.

    ``active_ids`` restricts regeneration to the scenes this run generates (the --scenes filter).
    """
    from audio import AudioPlayer

    player = AudioPlayer(speed=clock_speed)
    status_path = ctx.settings.layout().run_dir / "status.json"
    generation = ctx.generation

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="regen") as regen_pool:
        pending: dict[str, tuple[Future, int]] = {}
        passes = 0
        while not stop.is_set() and time.time() < deadline:
            passes += 1
            for step in graph.traversal():
                if stop.is_set() or time.time() >= deadline:
                    break
                b = bundles.get(step.scene.id)
                if b is None:
                    # a scene that failed generation: skip it on air, but still honour the cycle's update point
                    log.warning("no audio for %r yet; skipping", step.scene.title)
                else:
                    log.info("on air: %s (v%d, %.0fs)%s", step.scene.title, b.version, b.duration,
                             f" cycle {step.cycle_id} it {step.iteration}" if step.cycle_id else "")
                    write_json(status_path, {"on_air": step.scene.id, "title": step.scene.title, "version": b.version,
                                             "cycle": step.cycle_id, "iteration": step.iteration, "pass": passes,
                                             "generation": generation, "package": caster.current_package,
                                             "pending_regenerations": list(pending), "updated_at": _now()})
                    player.play(_asset_like(b))
                _reap(pending, bundles, caster)
                if step.update_due and step.cycle_id not in pending:
                    scenes = [sc for sc in graph.scenes_in_cycle(step.cycle_id) if active_ids is None or sc.id in active_ids]
                    if not scenes:
                        continue
                    generation += 1
                    rctx = dataclasses.replace(ctx, generation=generation, reason=f"cycle {step.cycle_id} update #{step.iteration // max(1, (graph.cycle_of(step.scene.node_key).repetitions_until_update or 1))}")
                    log.info("cycle %s hit its update interval; regenerating %d scene(s) as generation %d",
                             step.cycle_id, len(scenes), generation)
                    pending[step.cycle_id] = (regen_pool.submit(generate_scenes, scenes, rctx, stop), generation)
                if caster.publish_enabled and caster.current_package is None and caster.failed_publishes:
                    caster.push(bundles, reason="retry publish")
            if not loop:
                break
        # drain regenerations without blocking forever
        for cid, (fut, _g) in pending.items():
            log.info("waiting for regeneration of cycle %s to finish", cid)
            try:
                fut.result(timeout=900)
            except Exception:  # noqa: BLE001
                pass
        _reap(pending, bundles, caster)
    player.stop()


def _reap(pending: dict[str, tuple[Future, int]], bundles: dict[str, SceneBundle], caster: Broadcaster) -> None:
    """Swap finished regenerations in and publish a new package (only at a scene boundary)."""
    for cycle_id, (future, gen) in list(pending.items()):
        if not future.done():
            continue
        del pending[cycle_id]
        try:
            fresh = future.result()
        except Exception as error:  # noqa: BLE001
            log.error("cycle %s regeneration (generation %d) failed; previous audio stays on air: %s", cycle_id, gen, error)
            continue
        bundles.update(fresh)
        log.info("cycle %s regeneration complete: %d scene(s) refreshed (generation %d)", cycle_id, len(fresh), gen)
        caster.push(bundles, reason=f"cycle {cycle_id} regeneration (generation {gen})")


def _asset_like(b: SceneBundle):
    from artifacts import asset_from_json

    return asset_from_json(b.audio_json)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ai-livestream", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=None, help="saved broadcast configuration json (CONFIG_PATH)")
    parser.add_argument("--mode", choices=("full", "generate", "broadcast"), default="full",
                        help="full = generate, publish, then run the on-air loop; generate = stages 1-4 + publish once; "
                             "broadcast = rebuild from the run folder's bundles and loop")
    parser.add_argument("--scenes", default="", help="comma-separated node keys to restrict generation to (debugging)")
    parser.add_argument("--no-publish", action="store_true", help="build packages but do not upload them")
    parser.add_argument("--dry-run", action="store_true", help="run the on-air clock 30x faster and do not publish")
    parser.add_argument("--no-loop", action="store_true", help="stop after one pass through the graph")
    parser.add_argument("--log-level", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    if args.config:
        settings.config_path = args.config
    if args.log_level:
        settings.log_level = args.log_level
    os.environ["RUN_ID"] = settings.run_id       # worker processes must agree on the run folder
    os.environ["RUN_ROOT"] = str(settings.run_root)
    os.environ["CONFIG_PATH"] = str(settings.config_path)
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s  %(levelname)-7s  %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "urllib3", "faiss.loader"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if not settings.config_path.is_file():
        log.error("config not found: %s", settings.config_path)
        return 2

    from graph import BroadcastGraph

    graph = BroadcastGraph.from_config(settings.config_path)
    validation = graph.validate()
    if not validation.is_valid:
        for reason in validation.reasons:
            log.error("invalid graph: %s", reason)
        return 1

    layout = settings.layout().ensure()
    write_json(layout.run_json, {"run_id": settings.run_id, "config": str(settings.config_path), "started_at": _now(),
                                 "settings": settings.to_dict(), "argv": list(argv or sys.argv[1:])})
    scenes = graph.active_scenes()
    if args.scenes:
        keep = {k.strip() for k in args.scenes.split(",") if k.strip()}
        scenes = [s for s in scenes if s.node_key in keep]
    web_search = ",".join(k for k, o in graph.options.items() if o.do_web_search)
    ctx = RunContext(settings=settings, generation=_last_generation(layout, scenes) or 1, web_search_scenes=web_search)
    publish = settings.publish and not args.no_publish and not args.dry_run
    caster = Broadcaster(graph, settings, publish=publish)
    stop = threading.Event()
    desk = _start_desk_updater(publish)
    _install_signal_handlers(stop)
    deadline = time.time() + settings.max_hours * 3600
    log.info("run %s: %d scene(s), generation %d, publish=%s, max %.1f h, run folder %s", settings.run_id, len(scenes),
             ctx.generation, publish, settings.max_hours, layout.run_dir)

    try:
        if args.mode == "broadcast":
            bundles = _load_bundles(layout, scenes)
            if not bundles:
                log.error("no bundles in the run folder to broadcast from")
                return 1
        else:
            bundles = generate_scenes(scenes, ctx, stop)
        caster.push(bundles, reason=ctx.reason if ctx.generation == 1 else f"resume generation {ctx.generation}")
        if args.mode == "generate":
            return 0
        broadcast(graph, ctx, bundles, caster, clock_speed=30.0 if args.dry_run else 1.0, loop=not args.no_loop,
                  deadline=deadline, stop=stop, active_ids={s.id for s in scenes})
    except PipelineError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        log.warning("interrupted")
        return 130
    finally:
        if desk is not None:
            desk.stop()
        _stop_file(layout).unlink(missing_ok=True)
    log.info("broadcast loop ended (%s)", "stop requested" if stop.is_set() else
             "time limit reached" if time.time() >= deadline else "single pass done")
    return 0


def _start_desk_updater(publish: bool):
    """The website's live numbers (desk.json) are rebuilt every DESK_INTERVAL_S on their own thread."""
    if os.environ.get("DESK_ENABLED", "1") != "1":
        return None
    try:
        from desk.updater import DeskUpdater

        t = DeskUpdater(interval=float(os.environ.get("DESK_INTERVAL_S", "600")), publish=publish)
        t.start()
        log.info("desk updater started (every %ss, publish=%s)", int(t.interval), publish)
        return t
    except Exception:  # noqa: BLE001 - the numbers are a side channel; never block the broadcast on them
        log.exception("desk updater could not start")
        return None


def _last_generation(layout: RunLayout, scenes) -> int:
    gens = [max(_state(layout, s.id).values(), default=0) for s in scenes]
    return max(gens, default=0)


def _load_bundles(layout: RunLayout, scenes) -> dict[str, SceneBundle]:
    out = {}
    for s in scenes:
        p = layout.scene_dir(s.id) / "bundle.json"
        if p.is_file():
            o = read_json(p)
            if Path(o["audio_json"]["path"]).is_file():
                out[s.id] = SceneBundle(**o)
    return out


def _stop_file(layout: RunLayout) -> Path:
    return REPO_ROOT / ".run" / "STOP"


def _install_signal_handlers(stop: threading.Event) -> None:
    def handler(signum, _frame):
        log.warning("signal %s received; finishing the current scene and stopping", signum)
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handler)

    def watch_stop_file() -> None:
        p = REPO_ROOT / ".run" / "STOP"
        while not stop.is_set():
            if p.exists():
                log.warning("stop file %s found; stopping after the current scene", p)
                stop.set()
                break
            time.sleep(5)

    threading.Thread(target=watch_stop_file, daemon=True).start()


if __name__ == "__main__":
    sys.exit(main())

"""Backend pipeline entrypoint for the AI Livestream Hub.

This module owns *sequencing only*. Every unit of real work lives in a module
under ``src/modules/`` and is reached through that module's public interface
class. main.py must never call an LLM, embedding, NER, or NLI model directly —
those calls belong behind ``models.py``, which only the worker modules touch.

Pipeline stages, in order:

    1. Webscraping ........ webscrapper.WebScraper + quality_control.WebsiteScorer
    2. Split & cluster .... cluster.SentenceSplitter + cluster.SentenceClusterIndex
    3. Retrieve & write ... retrieval.Retriever + quality_control.ScriptHarness
    4. Script QC .......... quality_control.ScriptHarness
    5. Audio generation ... audio.AudioGenerator
    6. Broadcast .......... graph.BroadcastGraph + audio.AudioPlayer

Stages 3 and 4 share a single per-scene process on purpose: the QC revision loop
feeds the judge's verdict back to the writer, which needs the retrieved context
still in hand. Splitting them across a barrier would mean re-retrieving. Script
generation is a plain LLM call with system instructions, so it has no module of
its own — it lives inside ``ScriptHarness``, which owns the write/score/judge/
rewrite loop end to end.

CONCURRENCY MODEL (locked in — see ``run_scene_stage``)

    Processes within modules, threads within processes.

    One process is spawned per scene. A stage is a hard barrier: every scene
    process must reach a terminal state before the next stage begins. Any
    concurrency *inside* a scene — fetching that scene's websites, embedding its
    sentence pool — is threads, and is owned by the module, not by this file.

    Two consequences that constrain every module interface:

      * Stage payloads cross a process boundary, so every task and every result
        must be picklable. Modules hand back plain dataclasses and references,
        never open handles, live sockets, or loaded model objects.
      * Large intermediates (cleaned documents, cluster indices, audio) are
        persisted by ``database.Database`` and referenced by handle. Only the
        handle is returned across the boundary.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import sys
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from modules.audio import AudioGenerator, AudioPlayer
from modules.cluster import SentenceClusterIndex, SentenceSplitter
from modules.database import Database
from modules.graph import BroadcastGraph, Scene
from modules.quality_control import ScriptHarness, WebsiteScorer
from modules.retrieval import Retriever
from modules.webscrapper import WebScraper

log = logging.getLogger("livestream")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration types
#
# These belong to main.py rather than to any module: they describe how a stage
# reports back, not what a stage does.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SceneResult:
    """Outcome of one scene's work within one stage.

    Carries the PRD's warning/error distinction across the process boundary:
    a *warning* is a recoverable partial failure (one URL of several failed) and
    the run continues; an *error* is unrecoverable for that scene (no usable
    source at all) and aborts the whole generation.
    """

    scene_id: str
    ok: bool
    value: Any = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunContext:
    """Everything a worker process needs to reconstruct its own dependencies.

    Deliberately picklable and inert — paths and settings, never live objects.
    A worker builds its own ``Database``, model clients, and module interfaces
    from this on the far side of the process boundary.
    """

    config_path: Path
    database_root: Path
    mode: str
    max_workers: int
    scrape_top_k: int
    retrieval_top_k: int
    max_script_attempts: int


# ─────────────────────────────────────────────────────────────────────────────
# Parallel stage driver
# ─────────────────────────────────────────────────────────────────────────────


def run_scene_stage(
    stage_name: str,
    worker: Callable[[Scene, RunContext], SceneResult], # The actual stage we are running is passed in here 
    scenes: Sequence[Scene],
    ctx: RunContext,
) -> dict[str, SceneResult]:
    """Run ``worker`` once per scene, one process each, and wait for all of them.

    This is the single place the concurrency model is enforced. ``worker`` must
    be a module-level function (spawn-picklable) that takes a ``Scene`` plus the
    inert ``RunContext`` and returns a ``SceneResult``. Whatever threading it
    wants to do inside its process is its own business.

    Returns a result per scene, keyed by scene id. Never raises on a scene-level
    failure — a crashed worker is converted into a failed ``SceneResult`` so the
    caller can apply stage policy uniformly.
    """
    if not scenes:
        return {}

    log.info("[%s] starting %d scene process(es)", stage_name, len(scenes))
    results: dict[str, SceneResult] = {}

    # Process build -> use "spawn" method (doesn't copy from parent context like fork, starts new GIL + clean space for process)
    mp_context = mp.get_context("spawn") 

    # Use processes for each scene (truely parallel, as long as we have enough max_workers)
    with ProcessPoolExecutor(
        max_workers=min(ctx.max_workers, len(scenes)), # Max PROCESS workers -> how much processes can we run in parallel                              
        mp_context=mp_context,
        # TODO: hook models.py per-worker warmup here so a process loads its
        # embedding / NER / NLI weights once rather than per task.
        initializer=None,
    ) as pool: # pool -> interface with interacting with all of our (parallel) processes 
               #                                                  /- worker -> whatever stage (scraping, clustering, etc.) we are running
               #                                                  |      one worker / scene pair submitted for each processes                             
        futures: dict[Future[SceneResult], Scene] = {pool.submit(worker, scene, ctx): scene for scene in scenes}

        # Collect the Future objects as they complete (Future -> a "promise" \ contract of a certain task's future output — in this case, within a process)
        for future in as_completed(futures):
            scene = futures[future]                   # Extract scene str 
            try:
                result: SceneResult = future.result() # Extract SceneResult 
            except Exception as exc:  # a worker died outright
                log.exception("[%s] scene %r crashed", stage_name, scene.title)
                result = SceneResult(scene.id, ok=False, error=str(exc))
            results[scene.id] = result

    _log_stage_summary(stage_name, scenes, results)
    return results


def _log_stage_summary(
    stage_name: str, scenes: Sequence[Scene], results: dict[str, SceneResult]
) -> None:
    by_id = {scene.id: scene for scene in scenes}
    for scene_id, result in results.items():
        title = by_id[scene_id].title
        for warning in result.warnings:
            log.warning("[%s] %s: %s", stage_name, title, warning)
        if not result.ok:
            log.error("[%s] %s: %s", stage_name, title, result.error)


def assert_stage_ok(stage_name: str, results: dict[str, SceneResult]) -> None:
    """Apply the PRD's unrecoverable-failure policy at a stage barrier.

    Any scene reporting an error stops the whole generation: a broadcast with a
    missing scene is not a broadcast. Warnings have already been logged and are
    allowed through.
    """
    failed = [r for r in results.values() if not r.ok]
    if failed:
        raise PipelineError(
            f"{stage_name} failed for {len(failed)} scene(s); "
            "generation cannot continue"
        )


class PipelineError(RuntimeError):
    """Unrecoverable failure that returns the user to the graph editor."""


# ─────────────────────────────────────────────────────────────────────────────
# Stage workers
#
# Module-level so they survive pickling under the "spawn" start method. Each one
# runs inside its own process and builds its own module interfaces from ctx.
# ─────────────────────────────────────────────────────────────────────────────


def scrape_scene(scene: Scene, ctx: RunContext) -> SceneResult:
    """Stage 1 — gather, clean, score, and stage this scene's source documents.

    Threads live inside ``WebScraper``: the agent picks top-k sites, then fetches
    and cleans them concurrently. Scoring is deliberately *after* the full set is
    in hand, because ``website_score`` includes a cross-website entity-agreement
    term that has no meaning for a single document.
    """
    db = Database(ctx.database_root)
    scraper = WebScraper(top_k=ctx.scrape_top_k)
    scorer = WebsiteScorer()

    # Kick off scraping with concurrent threads (shares a GIL)
    documents = scraper.gather(scene)
    if not documents:
        return SceneResult(scene.id, ok=False, error="no sources could be retrieved")

    scored = scorer.score_documents(documents)
    accepted = [s for s in scored if s.accepted]
    warnings = [
        f"dropped {s.document.url} (website_score {s.score:.3f} below threshold)"
        for s in scored
        if not s.accepted
    ]

    if not accepted:
        return SceneResult(
            scene.id,
            ok=False,
            warnings=warnings,
            error="every source failed website quality control",
        )

    # All passage / pipe between different processes is with db (reading and writing to database) rather than pickling 
    db.stage_documents(scene.id, [s.document for s in accepted])
    return SceneResult(scene.id, ok=True, value=len(accepted), warnings=warnings)


def cluster_scene(scene: Scene, ctx: RunContext) -> SceneResult:
    """Stage 2 — split this scene's staged documents into a sentence pool, then cluster.

    The pool is flat and scene-wide: sentences from every accepted document for
    the scene go into one HDBSCAN run, so a cluster can span sources and
    cross-source agreement becomes visible to retrieval.

    Returns a *reference* to the persisted index, not the index itself — the
    fitted model does not cross the process boundary.
    """
    db = Database(ctx.database_root)
    documents = db.load_staged_documents(scene.id)

    sentences = SentenceSplitter().split(documents)
    if not sentences:
        return SceneResult(scene.id, ok=False, error="no sentences survived splitting")

    index = SentenceClusterIndex.build(sentences)
    ref = db.save_cluster_index(scene.id, index)
    return SceneResult(scene.id, ok=True, value=ref)


def write_script_for_scene(scene: Scene, ctx: RunContext) -> SceneResult:
    """Stages 3 and 4 — retrieve this scene's context, then hand it to the QC harness.

    One process because writing and scoring are a cycle, not a line: the harness
    runs write → score → judge → rewrite until the script is acceptable or the
    attempt budget is spent, and every rewrite needs the same retrieved sentences
    in hand. main.py deliberately does not drive that loop — it asks once and
    stores what comes back.
    """
    db = Database(ctx.database_root)
    index = db.load_cluster_index(scene.id)

    retriever = Retriever(index, top_k=ctx.retrieval_top_k)
    context = retriever.retrieve(scene)
    if not context.is_populated():
        return SceneResult(scene.id, ok=False, error="retrieval returned no sentences")

    harness = ScriptHarness(max_attempts=ctx.max_script_attempts)
    outcome = harness.produce(scene=scene, context=context)

    if not outcome.accepted:
        return SceneResult(
            scene.id,
            ok=False,
            warnings=outcome.warnings,
            error="no candidate script passed quality control",
        )

    ref = db.save_script(scene.id, outcome.script, outcome.score)
    return SceneResult(scene.id, ok=True, value=ref, warnings=outcome.warnings)


def generate_audio_for_scene(scene: Scene, ctx: RunContext) -> SceneResult:
    """Stage 5 — synthesize the accepted script and persist a playable asset."""
    db = Database(ctx.database_root)
    script = db.load_script(scene.id)

    generator = AudioGenerator(model=scene.tts_model, voice=scene.tts_voice)
    audio = generator.synthesize(scene=scene, script=script)
    ref = db.save_audio(scene.id, audio)
    return SceneResult(scene.id, ok=True, value=ref)


# ─────────────────────────────────────────────────────────────────────────────
# Generation — stages 1 through 5
# ─────────────────────────────────────────────────────────────────────────────


def generate_scenes(scenes: Sequence[Scene], ctx: RunContext) -> None:
    """Run the full generation pipeline over an arbitrary set of scenes.

    Called with every scene for the initial build, and with just a cycle's scenes
    when the orchestrator triggers a mid-broadcast regeneration. Each stage is a
    barrier; a stage error aborts the whole call.
    """
    # typehinting -> stages must be some iterable object (lists, tuples, etc.) containing a 
    # tuple of a string and a callable (function, class, etc.) returning a SceneResult class object 
    stages: Iterable[tuple[str, Callable[[Scene, RunContext], SceneResult]]] = (
        ("webscrape", scrape_scene),
        ("cluster", cluster_scene),
        ("script", write_script_for_scene),
        ("audio", generate_audio_for_scene),
    )

    #                 /- the callable in the iterable defined above 
    for stage_name, worker in stages:
        results = run_scene_stage(stage_name, worker, scenes, ctx)
        assert_stage_ok(stage_name, results)
        log.info("[%s] complete for %d scene(s)", stage_name, len(scenes))


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast — stage 6
# ─────────────────────────────────────────────────────────────────────────────


def broadcast(graph: BroadcastGraph, ctx: RunContext) -> None:
    """Walk the graph and play each scene's audio in order.

    Playback is strictly sequential — exactly one scene is on air at a time, and
    ``AudioPlayer.play`` blocks until the clip is finished before the traversal
    advances.

    Regeneration is the one thing that overlaps playback. When the traversal
    reports that a cycle has hit its ``repetitions_until_update``, that cycle's
    scenes are re-generated on a background thread which drives its own scene
    process pools. The freshly generated audio is swapped in only once the scene
    is not on air; if it isn't ready when the loop comes back around, the
    previous asset replays and the loop still counts toward the next update.
    """
    db = Database(ctx.database_root)
    player = AudioPlayer()

    # One background worker: regeneration is heavyweight and we never want two
    # regenerations of the same cycle in flight (PRD job rule 5).
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="regen") as regen_pool:
        pending: dict[str, Any] = {}  # cycle id -> Future

        for step in graph.traversal():
            asset = db.load_audio(step.scene.id)
            if asset is None:
                log.warning(
                    "no audio asset for %r; skipping to next scene", step.scene.title
                )
                continue

            log.info("on air: %s", step.scene.title)
            player.play(asset)  # blocks until the clip finishes

            _reap_regenerations(pending)

            if step.update_due and step.cycle_id not in pending:
                scenes = graph.scenes_in_cycle(step.cycle_id)
                log.info(
                    "cycle %s hit its update interval; regenerating %d scene(s)",
                    step.cycle_id,
                    len(scenes),
                )
                pending[step.cycle_id] = regen_pool.submit(generate_scenes, scenes, ctx)

    player.stop()


def _reap_regenerations(pending: dict[str, Any]) -> None:
    """Retire finished regeneration jobs so their cycle can be updated again.

    The swap itself is implicit: ``generate_scenes`` has already written the new
    audio asset, so the next ``db.load_audio`` picks it up. No "is it on air?"
    guard is needed — the asset is loaded before ``play`` blocks, so a
    regeneration that lands mid-clip cannot replace what is currently playing;
    it simply becomes visible the next time the traversal reaches that scene.

    All this does is clear the in-flight marker and surface failures without
    killing the stream.
    """
    for cycle_id, future in list(pending.items()):
        if not future.done():
            continue
        try:
            future.result()
            log.info("cycle %s regeneration complete", cycle_id)
        except Exception:
            log.exception(
                "cycle %s regeneration failed; continuing with previous audio",
                cycle_id,
            )
        del pending[cycle_id]


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Placeholder — grows as scripts/entrypoint.sh grows."""
    parser = argparse.ArgumentParser(
        prog="ai-livestream", description="Run the AI Livestream Hub backend pipeline."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="path to the saved broadcast configuration json",
    )
    parser.add_argument(
        "--database-root",
        type=Path,
        default=Path("output/database"),
        help="local database root (stands in for PostgreSQL + S3)",
    )
    parser.add_argument(
        "--mode",
        choices=("full", "generate", "broadcast"),
        default="full",
        help="full = generate then broadcast; generate = stages 1-5 only; "
        "broadcast = stage 6 against already-generated audio",
    )
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--scrape-top-k", type=int, default=8)
    parser.add_argument("--retrieval-top-k", type=int, default=5)
    parser.add_argument("--max-script-attempts", type=int, default=3)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    """Placeholder — cheap, fail-fast checks before any expensive work starts."""
    if not args.config.is_file():
        raise SystemExit(f"config not found: {args.config}")
    if args.max_workers < 1:
        raise SystemExit("--max-workers must be at least 1")
    args.database_root.mkdir(parents=True, exist_ok=True)
    # TODO: validate mode//artifact preconditions — "broadcast" needs a populated
    # database, "generate" must not clobber a run that is currently on air.


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    ctx = RunContext(
        config_path=args.config,
        database_root=args.database_root,
        mode=args.mode,
        max_workers=args.max_workers,
        scrape_top_k=args.scrape_top_k,
        retrieval_top_k=args.retrieval_top_k,
        max_script_attempts=args.max_script_attempts,
    )

    # The graph is the contract with the front half of the app: it is built once,
    # validated once, and is read-only for the rest of the run.
    graph = BroadcastGraph.from_config(args.config)
    validation = graph.validate()
    if not validation.is_valid:
        for reason in validation.reasons:
            log.error("invalid graph: %s", reason)
        return 1

    try:
        if args.mode in ("full", "generate"):
            generate_scenes(graph.active_scenes(), ctx)
        if args.mode in ("full", "broadcast"):
            broadcast(graph, ctx)
    except PipelineError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        log.warning("interrupted; run `cleanup.py` to clear partial run state")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())

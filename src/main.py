"""Backend pipeline entrypoint for the AI Livestream Hub.

This module owns *sequencing only*. Every unit of real work lives in a team
package under ``src/`` and is reached through that package's public interface
class. main.py must never call an LLM, embedding, NER, or NLI model directly —
those calls belong behind ``models/``, which only the team packages touch.

Pipeline stages, in order (one per team boundary — see the Team Interface
Contract and ``src/contracts/``):

    1. Sources ............ scraper.WebScraper + qc.WebsiteScorer   → list[ScoredDocument]
    2. Context ............ rag.Retriever                           → RetrievedContext
    3. Script ............. qc.ScriptHarness (+ writer.ScriptWriter) → ScriptOutcome
    4. Audio .............. audio.AudioGenerator                    → AudioAsset
    5. Broadcast .......... graph.BroadcastGraph + audio.AudioPlayer

Stage 3 is a loop, not a line: the harness runs write → score → judge → rewrite
inside one per-scene process, because every rewrite needs the same retrieved
context still in hand.

CONCURRENCY MODEL (locked in — see ``run_scene_stage``)

    Processes within modules, threads within processes.

    One process is spawned per scene. A stage is a hard barrier: every scene
    process must reach a terminal state before the next stage begins. Any
    concurrency *inside* a scene — fetching that scene's websites, embedding its
    sentence pool — is threads, and is owned by the module, not by this file.

    Two consequences that constrain every module interface:

      * Stage payloads cross a process boundary, so every task and every result
        must be picklable. Modules hand back the plain contract dataclasses,
        never open handles, live sockets, or loaded model objects.
      * There is no database in M1. Each stage's output travels back to this
        process in ``SceneResult.value`` and is handed to the next stage's
        worker for the same scene. Audio clips are files in ``--out-dir``; the
        ``AudioAsset`` pointing at each one is kept in memory for broadcast.
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

from audio import AudioGenerator, AudioPlayer
from contracts import AudioAsset, RetrievedContext, Scene, ScoredDocument, ScriptOutcome
from graph import BroadcastGraph
from qc import ScriptHarness, WebsiteScorer
from rag import Retriever
from scraper import WebScraper
from writer import ScriptWriter

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
    A worker builds its own model clients and module interfaces from this on
    the far side of the process boundary.
    """

    config_path: Path
    out_dir: Path
    mode: str
    max_workers: int
    scrape_max_threads: int
    retrieval_top_k: int
    max_script_attempts: int


# ─────────────────────────────────────────────────────────────────────────────
# Parallel stage driver
# ─────────────────────────────────────────────────────────────────────────────


def run_scene_stage(
    stage_name: str,
    worker: Callable[[Scene, RunContext, Any], SceneResult], # The actual stage we are running is passed in here
    scenes: Sequence[Scene],
    ctx: RunContext,
    upstream: dict[str, Any] | None = None,
) -> dict[str, SceneResult]:
    """Run ``worker`` once per scene, one process each, and wait for all of them.

    This is the single place the concurrency model is enforced. ``worker`` must
    be a module-level function (spawn-picklable) that takes a ``Scene``, the
    inert ``RunContext``, and that scene's output from the previous stage
    (``upstream[scene.id]``, or ``None`` for the first stage), and returns a
    ``SceneResult``. Whatever threading it wants to do inside its process is its
    own business.

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
        #                                                  |      the previous stage's output for this scene rides along, pickled like everything else
        futures: dict[Future[SceneResult], Scene] = {
            pool.submit(worker, scene, ctx, (upstream or {}).get(scene.id)): scene for scene in scenes
        }

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


def sources_stage(scene: Scene, ctx: RunContext, _upstream: None) -> SceneResult:
    """Stage 1 — gather, clean, and score this scene's source documents.

    Threads live inside ``WebScraper``: it fetches and cleans the scene's sites
    concurrently. Scoring is deliberately *after* the full set is in hand,
    because ``website_score`` includes a cross-website agreement term that has
    no meaning for a single document.

    ``value`` → the accepted ``list[ScoredDocument]``.
    """
    scraper = WebScraper(max_threads=ctx.scrape_max_threads)
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

    return SceneResult(scene.id, ok=True, value=accepted, warnings=warnings)


def context_stage(scene: Scene, ctx: RunContext, documents: list[ScoredDocument]) -> SceneResult:
    """Stage 2 — split, cluster, and retrieve this scene's context (all inside RAG).

    The cluster index is built and queried inside ``Retriever.retrieve`` and
    never leaves this process; only the ``RetrievedContext`` comes back.

    ``value`` → ``RetrievedContext``.
    """
    retriever = Retriever(top_k=ctx.retrieval_top_k)
    context = retriever.retrieve(scene, documents)
    if not context.is_populated():
        return SceneResult(scene.id, ok=False, error="retrieval returned no sentences")

    warnings = [f"no source answered: {query}" for query in context.unanswered_queries()]
    return SceneResult(scene.id, ok=True, value=context, warnings=warnings)


def script_stage(scene: Scene, ctx: RunContext, context: RetrievedContext) -> SceneResult:
    """Stage 3 — hand the context to the QC harness, which runs the write/score/judge loop.

    main.py deliberately does not drive that loop — it asks once and keeps what
    comes back.

    ``value`` → ``ScriptOutcome``.
    """
    harness = ScriptHarness(writer=ScriptWriter(), max_attempts=ctx.max_script_attempts)
    outcome = harness.produce(scene=scene, context=context)

    if not outcome.accepted:
        return SceneResult(
            scene.id,
            ok=False,
            warnings=outcome.warnings,
            error="no candidate script passed quality control",
        )

    return SceneResult(scene.id, ok=True, value=outcome, warnings=outcome.warnings)


def audio_stage(scene: Scene, ctx: RunContext, outcome: ScriptOutcome) -> SceneResult:
    """Stage 4 — synthesize the accepted script into a clip in ``out_dir``.

    ``value`` → ``AudioAsset``.
    """
    generator = AudioGenerator(out_dir=ctx.out_dir)
    audio = generator.synthesize(scene=scene, script=outcome.script)
    return SceneResult(scene.id, ok=True, value=audio)


# ─────────────────────────────────────────────────────────────────────────────
# Generation — stages 1 through 4
# ─────────────────────────────────────────────────────────────────────────────


def generate_scenes(scenes: Sequence[Scene], ctx: RunContext) -> dict[str, AudioAsset]:
    """Run the full generation pipeline over an arbitrary set of scenes.

    Called with every scene for the initial build, and with just a cycle's scenes
    when the orchestrator triggers a mid-broadcast regeneration. Each stage is a
    barrier; a stage error aborts the whole call.

    Each stage's per-scene outputs become the next stage's inputs. Returns the
    final ``AudioAsset`` per scene id.
    """
    # typehinting -> stages must be some iterable object (lists, tuples, etc.) containing a 
    # tuple of a string and a callable (function, class, etc.) returning a SceneResult class object 
    stages: Iterable[tuple[str, Callable[[Scene, RunContext, Any], SceneResult]]] = (
        ("sources", sources_stage),
        ("context", context_stage),
        ("script", script_stage),
        ("audio", audio_stage),
    )

    upstream: dict[str, Any] | None = None  # scene id -> previous stage's output for that scene
    #                 /- the callable in the iterable defined above 
    for stage_name, worker in stages:
        results = run_scene_stage(stage_name, worker, scenes, ctx, upstream)
        assert_stage_ok(stage_name, results)
        upstream = {scene_id: result.value for scene_id, result in results.items()}
        log.info("[%s] complete for %d scene(s)", stage_name, len(scenes))

    return upstream or {}


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast — stage 5
# ─────────────────────────────────────────────────────────────────────────────


def broadcast(graph: BroadcastGraph, ctx: RunContext, audio: dict[str, AudioAsset]) -> None:
    """Walk the graph and play each scene's audio in order.

    ``audio`` maps scene id → its current ``AudioAsset`` (the output of
    ``generate_scenes``). It lives in memory for the whole broadcast.

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
    player = AudioPlayer()

    # One background thread to handle regen jobs 
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="regen") as regen_pool:
        pending: dict[str, Any] = {}  # cycle id -> stores the future object created from the thread spawning new processes for regen scenes
                                      #                                                             

        for step in graph.traversal():
            asset = audio.get(step.scene.id)
            if asset is None:
                log.warning(
                    "no audio asset for %r; skipping to next scene", step.scene.title
                )
                continue

            log.info("on air: %s", step.scene.title)
            player.play(asset)  # blocks until the clip finishes

            _reap_regenerations(pending, audio)

            if step.update_due and step.cycle_id not in pending:
                scenes = graph.scenes_in_cycle(step.cycle_id)
                log.info(
                    "cycle %s hit its update interval; regenerating %d scene(s)",
                    step.cycle_id,
                    len(scenes),
                )
                pending[step.cycle_id] = regen_pool.submit(generate_scenes, scenes, ctx) # Submit is non-blocking -> moves on to the next traversal item while regen runs on processes  

    player.stop()


def _reap_regenerations(pending: dict[str, Any], audio: dict[str, AudioAsset]) -> None:
    """Retire finished regeneration jobs and swap their new audio in.

    The swap is just a dict update: the finished job's ``AudioAsset``s replace
    the old ones in ``audio``. No "is it on air?" guard is needed — the asset is
    looked up before ``play`` blocks, so a regeneration that lands mid-clip
    cannot replace what is currently playing; it simply becomes visible the next
    time the traversal reaches that scene.

    Also clears the in-flight marker and surfaces failures without killing the
    stream.
    """
    for cycle_id, future in list(pending.items()):
        if not future.done():
            continue
        try:
            audio.update(future.result())
            log.info("cycle %s regeneration complete", cycle_id)
        except Exception:
            log.exception(
                "cycle %s regeneration failed; continuing with previous audio",
                cycle_id,
            )
        del pending[cycle_id] # Manage the bookkeeping dictionary for cycle regenerations 


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
        "--out-dir",
        type=Path,
        default=Path("output/audio"),
        help="local folder where generated audio clips are written",
    )
    # "broadcast"-only mode (replaying audio from an earlier run) needs persistence,
    # which M1 does not have — it comes back once there is somewhere to load from.
    parser.add_argument(
        "--mode",
        choices=("full", "generate"),
        default="full",
        help="full = generate then broadcast; generate = stages 1-4 only",
    )
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--scrape-max-threads", type=int, default=8)
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
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # TODO: "generate" must not clobber a run that is currently on air.


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    ctx = RunContext(
        config_path=args.config,
        out_dir=args.out_dir,
        mode=args.mode,
        max_workers=args.max_workers,
        scrape_max_threads=args.scrape_max_threads,
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
        audio = generate_scenes(graph.active_scenes(), ctx)
        if args.mode == "full":
            broadcast(graph, ctx, audio)
    except PipelineError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        log.warning("interrupted; run `cleanup.py` to clear partial run state")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())

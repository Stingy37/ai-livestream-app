"""Scene — the shared, per-segment config handed to every stage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scene:
    """One playable node of the broadcast, and the unit of work for the pipeline.

    This is the object threaded through every stage: webscraping, retrieval,
    script writing, QC, and TTS all key off a ``Scene``. It crosses process
    boundaries, so it stays a plain picklable dataclass — no open handles, no
    loaded models.

    Division of labour with the config file: everything below ``node_key`` is
    authored by the user and read verbatim out of the json. ``id`` is minted at
    construction (see ``graph.BroadcastGraph.from_config``) and labels
    everything this scene produces.
    """

    id: str
    node_key: str

    title: str
    topic_description: str
    system_instructions: str
    # URLs supplied by the user. Empty means the scraper discovers its own sites
    # from ``title`` + ``topic_description``.
    sources: list[str]
    language: str

    # Resolved against the config's top-level ``defaults`` block at build time,
    # so downstream stages never have to know a default existed.
    script_model: str
    tts_model: str
    tts_voice: str

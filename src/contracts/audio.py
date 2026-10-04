"""Audio: TTS → broadcast loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioAsset:
    """One generated clip for one scene.

    Produced by ``audio.AudioGenerator.synthesize``; played by
    ``audio.AudioPlayer``.

    Carries ``duration_seconds`` because the broadcaster needs to know how long
    a scene will hold the air before it can reason about cycle timing, and
    reading that back off the file at play time is wasteful.
    """

    scene_id: str
    path: Path  # file in the local run folder
    duration_seconds: float
    sample_rate: int
    format: str = "wav"
    version: int = 1

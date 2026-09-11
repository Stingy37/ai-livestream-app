"""Contains methods in charge of decoding a given audio file and streaming to CABLE input of some virtual device.

Fits into app pipeline during graph traversal: the current node's audio file is expected as input into this module.
Also, seperately contains methods for generating and saving the audio to a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.graph import Scene


@dataclass
class AudioAsset:
    """One generated clip for one scene.

    Carries ``duration_seconds`` because the broadcaster needs to know how long
    a scene will hold the air before it can reason about cycle timing, and
    reading that back off the file at play time is wasteful.
    """

    scene_id: str
    path: Path
    duration_seconds: float
    sample_rate: int
    format: str = "wav"
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class AudioGenerator:
    """TTS: turns an accepted script into a playable asset.

    Generation only — this class knows nothing about playback. It runs inside a
    scene's process during stage 5, alongside every other scene's generator.
    """

    def __init__(self, model: str, voice: str | None = None) -> None:
        raise NotImplementedError

    def synthesize(self, scene: Scene, script: str) -> AudioAsset:
        """Synthesize the script and write the clip to disk.

        Uses ``scene.tts_model`` / ``scene.tts_voice`` as resolved on the scene,
        and ``scene.language`` where the model is multilingual. Returns the asset
        for the caller to persist — this class does not touch the database.
        """
        raise NotImplementedError


class AudioPlayer:
    """Decodes an asset and streams it to the virtual device's CABLE input.

    Used only during graph traversal, and only ever from the main process: there
    is exactly one output device and exactly one scene on air at a time.
    """

    def __init__(self, device: str | None = None) -> None:
        raise NotImplementedError

    def play(self, asset: AudioAsset) -> None:
        """Stream the clip to the device, blocking until it finishes.

        Blocking is the contract the traversal depends on — a scene must be
        fully played before the graph advances to the next node, so the caller
        can treat return as "this scene is off air".
        """
        raise NotImplementedError

    def stop(self) -> None:
        """Halt playback and release the device.

        Safe to call when nothing is playing, so termination and error paths can
        call it unconditionally.
        """
        raise NotImplementedError

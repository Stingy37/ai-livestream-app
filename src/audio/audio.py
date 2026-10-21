"""Audio (Integration): TTS with Kokoro, and the on-air clock the harness walks the graph with.

``AudioGenerator`` runs inside a scene's process during the audio stage and writes one wav per
scene into the run folder. ``AudioPlayer`` is not a sound device on this machine: playback happens
on the EC2 website. It is a *virtual* player that blocks for the clip's duration so the broadcast
loop advances scene by scene at the real pace (and raises ``update_due`` at the right moments).
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from config_env import Settings, write_json
from contracts import AudioAsset, LLMOutput, Scene

log = logging.getLogger(__name__)


class AudioGenerator:
    """TTS: turns an accepted script into a playable asset."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.settings = Settings.from_env()

    def synthesize(self, scene: Scene, script: LLMOutput) -> AudioAsset:
        """Synthesize the script and write ``<scene_id>.wav`` into ``out_dir``."""
        import soundfile as sf

        from models import tts_kokoro

        s = self.settings
        t0 = time.time()
        text = script.llm_output.strip() or f"No script is available for {scene.title} at this time."
        engine = (scene.tts_model or "kokoro").lower()
        if engine.startswith("moss"):
            # MOSS-TTS v1.5 (multilingual, e.g. Tagalog) runs as a shared server; see scripts/moss_tts_start.sh
            from models import tts_moss

            voice = scene.tts_voice or "default"
            audio, rate = tts_moss.synthesize(text, scene.language, voice)
        else:
            if engine != "kokoro":
                log.warning("[audio] %s: tts_model %r is not available locally; using Kokoro", scene.title, scene.tts_model)
            voice = scene.tts_voice or s.tts_default_voice
            try:
                tts_kokoro.voice_path(s.kokoro_dir, voice)
            except FileNotFoundError as error:
                log.warning("[audio] %s; falling back to %s", error, s.tts_default_voice)
                voice = s.tts_default_voice
            audio, rate = tts_kokoro.synthesize(text, voice, s.kokoro_dir, device=s.tts_device, sample_rate=s.tts_sample_rate)
        path = self.out_dir / f"{scene.id}.wav"
        tmp = path.with_suffix(".tmp.wav")
        sf.write(str(tmp), audio, rate, subtype="PCM_16")
        tmp.replace(path)
        duration = len(audio) / rate
        version = _next_version(path.with_suffix(".json"))
        asset = AudioAsset(scene_id=scene.id, path=path, duration_seconds=round(duration, 3), sample_rate=rate,
                           format="wav", version=version)
        write_json(path.with_suffix(".json"), {"scene_id": asset.scene_id, "path": str(path), "duration_seconds": asset.duration_seconds,
                                               "sample_rate": rate, "format": "wav", "version": version, "voice": voice, "engine": engine,
                                               "words": len(text.split()), "synth_s": round(time.time() - t0, 1)})
        log.info("[audio] %s: %.1fs of audio with %s in %.1fs", scene.title, duration, voice, time.time() - t0)
        return asset


def _next_version(meta_path: Path) -> int:
    try:
        import json

        return int(json.loads(meta_path.read_text()).get("version", 0)) + 1
    except (OSError, ValueError):
        return 1


class AudioPlayer:
    """Virtual player: ``play`` blocks for the clip's duration (minus nothing), ``stop`` interrupts."""

    def __init__(self, device: str | None = None, speed: float = 1.0) -> None:
        self.device = device
        self.speed = max(0.01, speed)      # >1 runs the on-air clock faster (dry runs)
        self._stop = threading.Event()

    def play(self, asset: AudioAsset) -> None:
        """Block until the clip 'finishes' on the virtual clock, or ``stop`` is called."""
        self._stop.clear()
        wait = max(0.0, asset.duration_seconds / self.speed)
        self._stop.wait(wait)

    def stop(self) -> None:
        self._stop.set()

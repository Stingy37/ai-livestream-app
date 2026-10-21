"""Client for the MOSS-TTS v1.5 server (src/tts_server/moss_server.py, scripts/moss_tts_start.sh)."""

from __future__ import annotations

import io
import os
import time
import wave

import numpy as np
import requests

MOSS_URL = os.environ.get("MOSS_URL", "http://127.0.0.1:8010")


def available(timeout: float = 3.0) -> bool:
    try:
        return requests.get(MOSS_URL + "/health", timeout=timeout).ok
    except requests.RequestException:
        return False


def synthesize(text: str, language: str, voice: str = "default", timeout: float = 1800.0, retries: int = 2) -> tuple[np.ndarray, int]:
    """Spoken audio (float32 mono) for ``text``; the server queues requests, so a long wait is normal."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(MOSS_URL + "/synthesize", json={"text": text, "language": language, "voice": voice}, timeout=timeout)
            if r.status_code >= 400:
                raise RuntimeError(f"MOSS HTTP {r.status_code}: {r.text[:200]}")
            with wave.open(io.BytesIO(r.content), "rb") as w:
                rate, frames = w.getframerate(), w.readframes(w.getnframes())
            return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32767, rate
        except (requests.RequestException, RuntimeError, wave.Error) as error:
            last = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"MOSS TTS unavailable: {last}")

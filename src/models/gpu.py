"""GPU time-sharing between the vLLM script writer and the full MOSS-TTS-v1.5 (24.8 GB).

The 35 GB MIG slice cannot hold both, so for the audio stage of MOSS scenes the harness:

    1. puts vLLM to sleep (level 1: weights parked in CPU RAM, KV cache freed; POST /sleep)
    2. lets the MOSS server load the full model (POST /load) and synthesize
    3. unloads MOSS (POST /unload) and wakes vLLM (POST /wake_up), then checks it answers

If vLLM does not come back healthy it is restarted with scripts/vllm_start.sh, so a failed wake never
leaves the stream without its writer. Needs vLLM started with sleep mode (scripts/vllm_start.sh does
that when VLLM_SLEEP_MODE=1, the default). Safe for one stream at a time: while vLLM sleeps nothing else
may call it (the stage barrier guarantees that within one harness).
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _vllm_base() -> str:
    return os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:8000/v1").rstrip("/").removesuffix("/v1")


def _moss_base() -> str:
    return os.environ.get("MOSS_URL", "http://127.0.0.1:8010").rstrip("/")


def vllm_is_sleeping() -> bool | None:
    try:
        r = requests.get(_vllm_base() + "/is_sleeping", timeout=10)
        return bool(r.json().get("is_sleeping")) if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def vllm_sleep(level: int = 1) -> None:
    t0 = time.time()
    r = requests.post(_vllm_base() + "/sleep", params={"level": level}, timeout=600)
    r.raise_for_status()
    log.info("[gpu] vLLM asleep (level %d) in %.0fs", level, time.time() - t0)


def vllm_healthy() -> bool:
    try:
        r = requests.post(_vllm_base() + "/v1/completions", timeout=120,
                          json={"model": os.environ.get("LOCAL_LLM_MODEL", "qwen3-8b"), "prompt": "OK", "max_tokens": 1})
        return r.ok
    except requests.RequestException:
        return False


def vllm_wake() -> None:
    t0 = time.time()
    try:
        requests.post(_vllm_base() + "/wake_up", timeout=600).raise_for_status()
        if vllm_healthy():
            log.info("[gpu] vLLM awake in %.0fs", time.time() - t0)
            return
        log.error("[gpu] vLLM woke but does not answer; restarting it")
    except requests.RequestException as error:
        log.error("[gpu] vLLM wake failed (%s); restarting it", error)
    subprocess.run(["bash", str(REPO_ROOT / "scripts" / "vllm_stop.sh")], check=False)
    subprocess.run(["bash", str(REPO_ROOT / "scripts" / "vllm_start.sh")], check=True)
    log.info("[gpu] vLLM restarted in %.0fs", time.time() - t0)


def moss_load() -> None:
    t0 = time.time()
    requests.post(_moss_base() + "/load", timeout=1800).raise_for_status()
    log.info("[gpu] MOSS loaded in %.0fs", time.time() - t0)


def moss_unload() -> None:
    try:
        requests.post(_moss_base() + "/unload", timeout=300).raise_for_status()
        log.info("[gpu] MOSS unloaded")
    except requests.RequestException as error:
        log.error("[gpu] MOSS unload failed: %s", error)


@contextlib.contextmanager
def tts_phase():
    """vLLM asleep and the full MOSS model loaded for the duration of the block; always restored."""
    slept = False
    try:
        if vllm_is_sleeping() is False:
            vllm_sleep()
            slept = True
        moss_load()
        yield
    finally:
        moss_unload()
        if slept or vllm_is_sleeping():
            vllm_wake()

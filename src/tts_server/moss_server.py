"""MOSS-TTS v1.5 synthesis server (runs in its own conda env: ~/.conda/envs/moss-tts).

One process holds the model on the GPU and serves every scene of every stream, one request at a time,
so 17 GB of weights are loaded once instead of once per scene process. Started by
scripts/moss_tts_start.sh; the audio stage talks to it through src/models/tts_moss.py.

    GET  /health                              {"ok": true, "model": ..., "loaded": bool}
    POST /synthesize   {"text", "language", "voice", "seed"?}  ->  audio/wav (16-bit mono, model rate)
    POST /load | /unload                      put the model on the GPU / free it (GPU time-sharing with vLLM,
                                              see src/models/gpu.py); /synthesize loads on demand too

Long scripts are split into chunks of about MOSS_CHUNK_CHARS characters at sentence boundaries and
synthesized in order with a short pause between them. Voice consistency: MOSS invents a voice when no
reference is given, so ``voice`` names a reference clip in MOSS_VOICE_DIR (``<voice>.wav``). The first
request for a voice that has no clip creates one: a short neutral sentence in the requested language,
synthesized with a fixed seed and saved, then used as the reference for everything after it.

Environment: MOSS_MODEL_PATH, MOSS_CODEC_PATH, MOSS_HOST, MOSS_PORT, MOSS_VOICE_DIR, MOSS_CHUNK_CHARS,
MOSS_MAX_NEW_TOKENS, MOSS_DEVICE.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

log = logging.getLogger("moss")

MODEL_PATH = os.environ.get("MOSS_MODEL_PATH", "/home/andyshi2/pre-models/MOSS-TTS-v1.5")
CODEC_PATH = os.environ.get("MOSS_CODEC_PATH", "/home/andyshi2/pre-models/MOSS-Audio-Tokenizer")
HOST = os.environ.get("MOSS_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOSS_PORT", "8010"))
VOICE_DIR = Path(os.environ.get("MOSS_VOICE_DIR", str(Path(__file__).resolve().parents[2] / "model_weights" / "moss_voices")))
CHUNK_CHARS = int(os.environ.get("MOSS_CHUNK_CHARS", "420"))
MAX_NEW_TOKENS = int(os.environ.get("MOSS_MAX_NEW_TOKENS", "4096"))
DEVICE = os.environ.get("MOSS_DEVICE", "cuda")
PAUSE_S = 0.28

LANGUAGE_NAMES = {"en": "English", "tl": "Tagalog", "fil": "Tagalog", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
                  "vi": "Vietnamese", "th": "Thai", "ms": "Malay", "es": "Spanish"}
VOICE_SEED_TEXT = {
    "Tagalog": "Magandang araw. Narito ang pinakabagong ulat tungkol sa panahon at sa mga babala ng ahensya.",
    "English": "Hello. Here is the latest report on the weather and the warnings issued by the agencies.",
}


class Engine:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.model = None
        self.processor = None
        self.rate = 24000

    def load(self) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        torch.backends.cuda.enable_cudnn_sdp(False)
        t0 = time.time()
        kw = {"trust_remote_code": True}
        if CODEC_PATH:
            kw["codec_path"] = CODEC_PATH
        self.processor = AutoProcessor.from_pretrained(MODEL_PATH, **kw)
        self.processor.audio_tokenizer = self.processor.audio_tokenizer.to(DEVICE)
        dtype = torch.bfloat16 if DEVICE == "cuda" else torch.float32
        self.model = AutoModel.from_pretrained(MODEL_PATH, trust_remote_code=True, attn_implementation="sdpa",
                                               torch_dtype=dtype).to(DEVICE).eval()
        self.rate = int(self.processor.model_config.sampling_rate)
        used = torch.cuda.memory_allocated() / 1e9 if DEVICE == "cuda" else 0.0
        log.info("MOSS loaded in %.0fs from %s (rate %d Hz, GPU allocated %.1f GB)", time.time() - t0, MODEL_PATH, self.rate, used)

    def unload(self) -> None:
        import gc

        import torch

        with self.lock:
            if self.model is None:
                return
            self.model = None
            self.processor = None
            gc.collect()
            torch.cuda.empty_cache()
            log.info("MOSS unloaded; GPU allocated %.1f GB", torch.cuda.memory_allocated() / 1e9)

    def ensure_loaded(self) -> None:
        with self.lock:
            if self.model is None:
                self.load()

    def _generate(self, text: str, language: str, reference: str | None, seed: int | None) -> np.ndarray:
        import torch

        if seed is not None:
            torch.manual_seed(seed)
        msg = self.processor.build_user_message(text=text, language=language, reference=[reference] if reference else None)
        batch = self.processor([[msg]], mode="generation")
        with torch.no_grad():
            out = self.model.generate(input_ids=batch["input_ids"].to(DEVICE), attention_mask=batch["attention_mask"].to(DEVICE),
                                      max_new_tokens=MAX_NEW_TOKENS)
        for message in self.processor.decode(out):
            if message is None:
                continue
            audio = message.audio_codes_list[0].detach().float().cpu().numpy()
            if audio.ndim == 2:                   # [channels, samples] (stereo codec) -> mono
                audio = audio.mean(axis=0)
            return audio.astype(np.float32)
        raise RuntimeError("MOSS returned no audio")

    def voice_reference(self, voice: str, language: str) -> str | None:
        if not voice or voice in ("none", "random"):
            return None
        name = re.sub(r"[^A-Za-z0-9_\-]", "_", f"{voice}_{language}" if voice == "default" else voice)
        path = VOICE_DIR / f"{name}.wav"
        if not path.is_file():
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            seed_text = VOICE_SEED_TEXT.get(language, VOICE_SEED_TEXT["English"])
            audio = self._generate(seed_text, language, None, seed=1234)
            write_wav(path, audio, self.rate)
            log.info("created reference voice %s (%.1fs)", path, len(audio) / self.rate)
        return str(path)

    def synthesize(self, text: str, language_code: str, voice: str, seed: int | None) -> tuple[np.ndarray, int]:
        language = LANGUAGE_NAMES.get((language_code or "en").lower().split("-")[0], language_code or "English")
        with self.lock:
            if self.model is None:
                self.load()
            ref = self.voice_reference(voice, language)
            pieces = []
            for k, chunk in enumerate(chunks(text, CHUNK_CHARS)):
                pieces.append(self._generate(chunk, language, ref, None if seed is None else seed + k))
                pieces.append(np.zeros(int(PAUSE_S * self.rate), dtype=np.float32))
            if not pieces:
                raise ValueError("empty text")
            return np.concatenate(pieces), self.rate


def chunks(text: str, limit: int) -> list[str]:
    """Sentence-boundary chunks of at most ~limit characters (a single long sentence stays whole)."""
    sentences = re.findall(r"[^.!?。！？]+[.!?。！？]+[\"')\]]*|[^.!?。！？]+$", re.sub(r"\s+", " ", text).strip())
    out, cur = [], ""
    for s in (x.strip() for x in sentences):
        if not s:
            continue
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def write_wav(path_or_buf, audio: np.ndarray, rate: int) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(path_or_buf if not isinstance(path_or_buf, Path) else str(path_or_buf), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


ENGINE = Engine()


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._json(200, {"ok": True, "model": MODEL_PATH, "loaded": ENGINE.model is not None})
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path in ("/load", "/unload"):
            try:
                ENGINE.ensure_loaded() if self.path == "/load" else ENGINE.unload()
                return self._json(200, {"ok": True, "loaded": ENGINE.model is not None})
            except Exception as error:  # noqa: BLE001
                log.exception("%s failed", self.path)
                return self._json(500, {"error": f"{type(error).__name__}: {error}"})
        if self.path != "/synthesize":
            return self._json(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            text = str(req.get("text") or "").strip()
            if not text:
                return self._json(400, {"error": "text is required"})
            t0 = time.time()
            audio, rate = ENGINE.synthesize(text, str(req.get("language") or "en"), str(req.get("voice") or "default"), req.get("seed"))
            buf = io.BytesIO()
            write_wav(buf, audio, rate)
            data = buf.getvalue()
            log.info("synthesized %d chars -> %.1fs audio in %.1fs", len(text), len(audio) / rate, time.time() - t0)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Sample-Rate", str(rate))
            self.end_headers()
            self.wfile.write(data)
        except Exception as error:  # noqa: BLE001
            log.exception("synthesis failed")
            self._json(500, {"error": f"{type(error).__name__}: {error}"})

    def log_message(self, fmt, *args) -> None:
        pass


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s  %(levelname)-7s  %(message)s")
    if os.environ.get("MOSS_PRELOAD", "0") == "1":
        ENGINE.load()
    log.info("MOSS TTS server on http://%s:%d", HOST, PORT)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

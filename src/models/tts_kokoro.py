"""Kokoro-82M text-to-speech, loaded from the local weights folder (KOKORO_DIR).

Weights: ``config.json`` + ``kokoro-v1_0.pth`` + ``voices/<voice>.pt`` (downloaded once into
~/pre-models/Kokoro-82M). One model per process, built on first use; voices are cached by name.
``lang_code`` 'a' = American English, 'b' = British English, 'j' = Japanese, 'z' = Mandarin (the voice prefix decides:
a*/b*/j*/z*; Japanese needs ``misaki[ja]``, Mandarin ``misaki[zh]``).
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_pipelines: dict[str, object] = {}


def _load(kokoro_dir: Path, device: str):
    global _model
    import torch
    from kokoro import KModel

    if _model is None:
        dev = device if (device != "cuda" or torch.cuda.is_available()) else "cpu"
        _model = KModel(config=str(kokoro_dir / "config.json"), model=str(kokoro_dir / "kokoro-v1_0.pth")).to(dev).eval()
        log.info("Kokoro loaded on %s from %s", dev, kokoro_dir)
    return _model


def _pipeline(kokoro_dir: Path, device: str, lang_code: str):
    from kokoro import KPipeline

    with _lock:
        p = _pipelines.get(lang_code)
        if p is None:
            p = KPipeline(lang_code=lang_code, model=_load(kokoro_dir, device), repo_id="hexgrad/Kokoro-82M")
            _pipelines[lang_code] = p
        return p


def voice_path(kokoro_dir: Path, voice: str) -> Path:
    p = kokoro_dir / "voices" / f"{voice}.pt"
    if not p.is_file():
        raise FileNotFoundError(f"voice {voice!r} not found at {p}; download it into {kokoro_dir}/voices/")
    return p


def synthesize(text: str, voice: str, kokoro_dir: Path, device: str = "cuda", speed: float = 1.0,
               sample_rate: int = 24000) -> tuple[np.ndarray, int]:
    """Spoken audio (float32 mono) for ``text`` with ``voice``; sentences are synthesised in order."""
    lang = {"b": "b", "j": "j", "z": "z"}.get(voice[:1], "a")
    pipe = _pipeline(Path(kokoro_dir), device, lang)
    vp = str(voice_path(Path(kokoro_dir), voice))
    text = normalise_ja(text) if lang == "j" else normalise_zh(text) if lang == "z" else normalise_for_speech(text)
    chunks: list[np.ndarray] = []
    with _lock:
        for _gs, _ps, audio in pipe(text, voice=vp, speed=speed, split_pattern=r"\n+"):
            if audio is None:
                continue
            arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
            chunks.append(arr.astype(np.float32))
            # a short pause between paragraphs/sentences keeps the delivery natural
            chunks.append(np.zeros(int(0.18 * sample_rate), dtype=np.float32))
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")
    return np.concatenate(chunks), sample_rate


_ABBREV = {"km/h": "kilometres per hour", "kph": "kilometres per hour", "hPa": "hectopascals", "mm": "millimetres",
           "m/s": "metres per second", "kt": "knots", "UTC": "U T C", "JST": "Japan time", "PHT": "Philippine time"}


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?Z?(?:\s*UTC)?")


def _spoken_iso(m: re.Match) -> str:
    y, mo, d, hh, mm = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
    when = "midnight" if (hh, mm) == (0, 0) else f"{hh:02d}:{mm:02d}"
    return f"{_MONTHS[mo - 1]} {d} at {when} UTC"


def normalise_for_speech(text: str) -> str:
    """Spell out units, timestamps and coordinates; one sentence per line (Kokoro splits on newlines)."""
    text = _ISO.sub(_spoken_iso, text)
    text = re.sub(r"(?<=\d)°?\s?N\b", " north", text)
    text = re.sub(r"(?<=\d)°?\s?E\b", " east", text)
    for k, v in _ABBREV.items():
        text = re.sub(rf"(?<=\d)\s*{re.escape(k)}\b", f" {v}", text)
    text = re.sub(r"(?<=\d)°N", " degrees north", text)
    text = re.sub(r"(?<=\d)°E", " degrees east", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[.!?])\s+(?=[A-Z\"'(])", "\n", text)
    return text


# Japanese: the translated script keeps agency names, units and coordinates as in the English draft; say them the
# way a Japanese newsreader would (Kokoro's Japanese G2P reads digits itself)
_JA_AGENCY = {"JMA": "気象庁", "JTWC": "米軍合同台風警報センター", "PAGASA": "フィリピン気象庁", "CWA": "台湾の中央気象署",
              "NOAA": "アメリカ海洋大気庁", "UTC": "協定世界時", "JST": "日本時間"}
_JA_UNITS = [("km/h", "キロ毎時"), ("kph", "キロ毎時"), ("m/s", "メートル"), ("hPa", "ヘクトパスカル"), ("mm", "ミリ"),
             ("km", "キロ"), ("kt", "ノット"), ("knots", "ノット"), ("%", "パーセント"), ("m", "メートル")]


def normalise_ja(text: str) -> str:
    """Japanese script for Kokoro 'j': agency acronyms and units in Japanese, coordinates as 北緯/東経, clock times as
    時/分, one sentence per line."""
    text = _ISO.sub(lambda m: f"協定世界時{int(m.group(2))}月{int(m.group(3))}日{int(m.group(4))}時", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*°?\s*N\b", r"北緯\1度", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*°?\s*E\b", r"東経\1度", text)
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda m: f"{int(m.group(1))}時" + (f"{int(m.group(2))}分" if int(m.group(2)) else ""), text)
    for k, v in _JA_UNITS:
        text = re.sub(rf"(?<=\d)\s*{re.escape(k)}(?![A-Za-z])", v, text)
    for k, v in _JA_AGENCY.items():
        text = re.sub(rf"(?<![A-Za-z]){k}(?![A-Za-z])", v, text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[。！？])\s*", "\n", text).strip()


# Mandarin (Taiwan): the same idea for Kokoro 'z', in the words a Taiwanese newsreader uses (氣象署, 百帕, 公里, 公尺)
_ZH_AGENCY = {"JMA": "日本氣象廳", "JTWC": "美軍聯合颱風警報中心", "PAGASA": "菲律賓氣象局", "CWA": "中央氣象署",
              "NOAA": "美國國家海洋暨大氣總署", "UTC": "世界協調時間", "JST": "日本時間", "PHT": "菲律賓時間", "PAR": "菲律賓責任區"}
_ZH_UNITS = [("hPa", "百帕"), ("mm", "毫米"), ("km", "公里"),
             ("kt", "節"), ("knots", "節"), ("%", "%"), ("m", "公尺")]


def normalise_zh(text: str) -> str:
    """Mandarin script for Kokoro 'z': agency acronyms and units in Chinese, coordinates as 北緯/東經, clock times as
    點/分, one sentence per line."""
    # no \b before the digits: CJK characters count as word characters
    text = re.sub(_ISO.pattern.removeprefix(r"\b"), lambda m: f"世界協調時間{int(m.group(2))}月{int(m.group(3))}日{int(m.group(4))}點", text)
    # speeds the way they are read in Taiwan: 每小時215公里, 每秒85公尺 (keeping a 每秒 the translation already wrote)
    text = re.sub(r"(?:每小時\s*)?(\d+(?:\.\d+)?)\s*(?:km/h|kph)(?![A-Za-z])", r"每小時\1公里", text)
    text = re.sub(r"(?:每秒\s*)?(\d+(?:\.\d+)?)\s*m/s(?![A-Za-z])", r"每秒\1公尺", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*°?\s*N\b", r"北緯\1度", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*°?\s*E\b", r"東經\1度", text)
    text = re.sub(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])", lambda m: f"{int(m.group(1))}點" + (f"{int(m.group(2))}分" if int(m.group(2)) else ""), text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"百分之\1", text)
    for k, v in _ZH_UNITS:
        text = re.sub(rf"(?<=\d)\s*{re.escape(k)}(?![A-Za-z])", v, text)
    for k, v in _ZH_AGENCY.items():
        text = re.sub(rf"(?<![A-Za-z]){k}(?![A-Za-z])", v, text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[。！？])\s*", "\n", text).strip()

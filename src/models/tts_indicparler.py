"""AI4Bharat Indic Parler-TTS: Indian English narration (and Telugu), which Kokoro and MMS cannot give.

    audio, rate = synthesize("Cyclone Murasu is about 450 km east of Chennai.", "en", voice="Thoma")

Model: ai4bharat/indic-parler-tts (0.9B, Apache 2.0; gated on Hugging Face, so accept its terms once, then
scripts/indic_parler_download.sh) under PARLER_DIR (default /home/andyshi2/pre-models/indic-parler-tts), with the
description tokenizer saved beside it in description_tokenizer/ so HF_HUB_OFFLINE=1 works. Needs
``pip install git+https://github.com/huggingface/parler-tts.git``. Loaded once per process.

The voice is a sentence that describes it and names one of the model's speakers (Thoma: Indian English, male; Mary:
Indian English, female; Prakash: Telugu) and its delivery: "Thoma" is brisk and alert, "Thoma:urgent" faster and
more emphatic for landfall and warnings. The same description and a fixed seed for every sentence keep the voice
steady from scene to scene. Text is spoken sentence by sentence with short pauses (a long input drifts and rushes),
and numbers, units and agency acronyms are spelled out the way an Indian newsreader says them.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

PARLER_DIR = Path(os.environ.get("PARLER_DIR", "/home/andyshi2/pre-models/indic-parler-tts"))
DEFAULT_VOICE = {"en": "Thoma", "te": "Prakash"}
# Delivery, picked per scene with "<speaker>:<style>" (e.g. "Thoma:urgent" on the landfall and warnings scenes). The
# words are the attributes the model was trained to follow: pace, expressiveness, pitch, recording quality.
QUALITY = " The recording is of very high quality, with the voice sounding clear and very close up and no background noise."
STYLES = {
    "steady": "{voice} speaks in a clear, confident and slightly expressive news-reader tone at a moderately fast pace, "
              "with an Indian English accent and a sense of urgency." + QUALITY,
    "urgent": "{voice} speaks in an urgent, energetic and highly expressive news-reader tone at a fast pace, with a slightly "
              "high pitch and an Indian English accent, stressing the key words." + QUALITY,
    "te": "{voice} speaks in a clear, confident news-reader tone at a moderately fast pace." + QUALITY,
}
STYLE = os.environ.get("PARLER_STYLE", "")        # one description for every scene, overriding STYLES
SEED = 7
MAX_CHARS = 260                                   # longer sentences are split at commas
_CACHE: dict[str, tuple] = {}


def default_voice(language: str) -> str:
    return DEFAULT_VOICE.get((language or "en").lower().split("-")[0], DEFAULT_VOICE["en"])


def description(voice: str | None, language: str = "en") -> str:
    """The voice description for "Thoma" / "Thoma:urgent" (Telugu has one delivery)."""
    lang = (language or "en").lower().split("-")[0]
    speaker, _, style = (voice or default_voice(lang)).partition(":")
    if STYLE:
        return STYLE.format(voice=speaker)
    if lang != "en":
        return STYLES["te"].format(voice=speaker)
    if style and style not in STYLES:
        raise ValueError(f"unknown delivery {style!r} (have: steady, urgent)")
    return STYLES[style or "steady"].format(voice=speaker)


# ---- English text -> what a newsreader says ------------------------------------------------------------------------
EN_UNITS = [(r"km/h|kmph|kph", "kilometres per hour"), (r"\bkm\b", "kilometres"), (r"\bhPa\b", "hectopascals"),
            (r"\bmm\b", "millimetres"), (r"(?<=\d)\s*m\b", " metres"), (r"%", " per cent"), (r"°", " degrees ")]
EN_ACRONYMS = {"IMD": "I M D", "JTWC": "J T W C", "IST": "Indian Standard Time", "UTC": "U T C", "NDRF": "N D R F",
               "SDRF": "S D R F", "RSMC": "R S M C", "INCOIS": "in-coys"}


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]


def _say_day(m: re.Match) -> str:
    try:
        from num2words import num2words
    except ImportError:
        return m.group(0)
    return f"{num2words(int(m.group(1)), lang='en_IN', to='ordinal')} {m.group(2)}"


def _say_number(m: re.Match) -> str:
    try:
        from num2words import num2words
    except ImportError:                                     # the voice reads digits itself, less evenly
        return m.group(0)
    whole, frac = m.group(1).replace(",", ""), m.group(2)
    out = num2words(int(whole), lang="en_IN")
    if frac:
        out += " point " + " ".join(num2words(int(d), lang="en_IN") for d in frac)
    return f" {out} "


def normalise_en(text: str) -> str:
    text = re.sub(r"(\d)\s*[-–]\s*(\d)", r"\1 to \2", text)                   # 100-110 km/h -> 100 to 110 km/h
    text = re.sub(r"\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b",
                  lambda m: f"{int(m.group(1))}{'' if m.group(2) == '00' else ' ' + m.group(2)} {m.group(3).lower()}", text)
    text = re.sub(r"(?<=\d)\s*\b(am|pm)\b", lambda m: " " + " ".join(m.group(1).upper()), text)   # 2 pm -> 2 P M
    for k, v in EN_ACRONYMS.items():
        text = re.sub(rf"\b{k}\b", v, text)
    for rx, repl in EN_UNITS:
        text = re.sub(rx, f" {repl}", text)
    text = re.sub(rf"\b(\d{{1,2}}) ({'|'.join(MONTHS)})\b", _say_day, text)    # 26 October -> twenty-sixth October
    text = re.sub(r"(\d[\d,]*)(?:\.(\d+))?", _say_number, text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[list[str]]:
    """Lines of sentences; a sentence over MAX_CHARS is cut at commas."""
    out = []
    for line in [l for l in text.splitlines() if l.strip()]:
        sents = []
        for s in [s.strip() for s in re.split(r"(?<=[.!?।])\s+", line) if s.strip()]:
            while len(s) > MAX_CHARS and "," in s[:MAX_CHARS]:
                cut = s.rfind(",", 0, MAX_CHARS)
                sents.append(s[:cut].strip() + ",")
                s = s[cut + 1:].strip()
            sents.append(s)
        out.append(sents)
    return out


def _load(device: str):
    if device not in _CACHE:
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        model = ParlerTTSForConditionalGeneration.from_pretrained(PARLER_DIR).to(device).eval()
        desc_dir = PARLER_DIR / "description_tokenizer"
        desc_tok = AutoTokenizer.from_pretrained(desc_dir if desc_dir.is_dir() else model.config.text_encoder._name_or_path)
        _CACHE[device] = (AutoTokenizer.from_pretrained(PARLER_DIR), desc_tok, model)
    return _CACHE[device]


def synthesize(text: str, language: str = "en", voice: str | None = None, device: str = "cuda",
               sentence_pause: float = 0.3, line_pause: float = 0.55) -> tuple[np.ndarray, int]:
    import torch

    lang = (language or "en").lower().split("-")[0]
    if lang not in DEFAULT_VOICE:
        raise ValueError(f"Indic Parler-TTS is set up for {', '.join(DEFAULT_VOICE)}, not {language!r}")
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    tok, desc_tok, model = _load(device)
    rate = model.config.sampling_rate
    desc = desc_tok(description(voice, lang), return_tensors="pt").to(device)
    out: list[np.ndarray] = []
    for line in _sentences(text):
        for sent in line:
            spoken = normalise_en(sent) if lang == "en" else sent
            if not spoken:
                continue
            prompt = tok(spoken, return_tensors="pt").to(device)
            torch.manual_seed(SEED)                             # same voice texture every time
            with torch.no_grad():
                wav = model.generate(input_ids=desc.input_ids, attention_mask=desc.attention_mask,
                                     prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask)
            out += [wav.float().cpu().numpy().squeeze(), np.zeros(int(rate * sentence_pause), dtype=np.float32)]
        out.append(np.zeros(int(rate * line_pause), dtype=np.float32))
    if not out:
        raise ValueError("nothing to say")
    audio = np.concatenate(out)
    peak = float(np.abs(audio).max()) or 1.0
    return (audio / peak * 0.9).astype(np.float32), rate

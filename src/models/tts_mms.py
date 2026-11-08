"""Meta MMS-TTS (VITS) voices for Telugu and Tamil, which Kokoro does not speak.

    audio, rate = synthesize("అర్నాబ్ తుఫాను ...", "te")

Models: facebook/mms-tts-tel and facebook/mms-tts-tam under MMS_DIR (default /home/andyshi2/pre-models), loaded once
per process. Licence CC-BY-NC 4.0 (non-commercial). The vocabularies are native-script only, so digits are read out
as words first (Telugu with num2words, Tamil with the small converter below), and text is spoken sentence by sentence
with short pauses (one long VITS pass drifts and rushes).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

MODELS = {"te": "mms-tts-tel", "ta": "mms-tts-tam"}
MMS_DIR = Path(os.environ.get("MMS_DIR", "/home/andyshi2/pre-models"))
_CACHE: dict[str, tuple] = {}

# ---- numbers -> words ------------------------------------------------------------------------------------------
TA_UNITS = ["பூஜ்ஜியம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது"]
TA_TEENS = ["பத்து", "பதினொன்று", "பன்னிரண்டு", "பதிமூன்று", "பதினான்கு", "பதினைந்து", "பதினாறு", "பதினேழு", "பதினெட்டு", "பத்தொன்பது"]
TA_TENS = {2: ("இருபது", "இருபத்தி"), 3: ("முப்பது", "முப்பத்தி"), 4: ("நாற்பது", "நாற்பத்தி"), 5: ("ஐம்பது", "ஐம்பத்தி"),
           6: ("அறுபது", "அறுபத்தி"), 7: ("எழுபது", "எழுபத்தி"), 8: ("எண்பது", "எண்பத்தி"), 9: ("தொண்ணூறு", "தொண்ணூற்றி")}
TA_HUNDREDS = {1: ("நூறு", "நூற்றி"), 2: ("இருநூறு", "இருநூற்றி"), 3: ("முந்நூறு", "முந்நூற்றி"), 4: ("நானூறு", "நானூற்றி"),
               5: ("ஐநூறு", "ஐநூற்றி"), 6: ("அறுநூறு", "அறுநூற்றி"), 7: ("எழுநூறு", "எழுநூற்றி"), 8: ("எண்ணூறு", "எண்ணூற்றி"),
               9: ("தொள்ளாயிரம்", "தொள்ளாயிரத்தி")}


def ta_number(n: int) -> str:
    """Tamil words for 0 <= n < 1,000,000 (e.g. 650 -> அறுநூற்றி ஐம்பது)."""
    if n < 10:
        return TA_UNITS[n]
    if n < 20:
        return TA_TEENS[n - 10]
    if n < 100:
        t, u = divmod(n, 10)
        return TA_TENS[t][0] if not u else f"{TA_TENS[t][1]} {TA_UNITS[u]}"
    if n < 1000:
        h, r = divmod(n, 100)
        return TA_HUNDREDS[h][0] if not r else f"{TA_HUNDREDS[h][1]} {ta_number(r)}"
    k, r = divmod(n, 1000)
    head = "ஆயிரம்" if k == 1 else "இரண்டாயிரம்" if k == 2 else f"{ta_number(k)} ஆயிரம்"
    if not r:
        return head
    if k == 2:
        head = "இரண்டாயிரம்"
    return f"{head[:-2]}த்தி {ta_number(r)}"          # ஆயிரம் -> ஆயிரத்தி ..., இரண்டாயிரம் -> இரண்டாயிரத்தி ...


TE_UNITS = ["సున్నా", "ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది"]
TE_TEENS = ["పది", "పదకొండు", "పన్నెండు", "పదమూడు", "పద్నాలుగు", "పదిహేను", "పదహారు", "పదిహేడు", "పద్దెనిమిది", "పందొమ్మిది"]
TE_TENS = {2: "ఇరవై", 3: "ముప్పై", 4: "నలభై", 5: "యాభై", 6: "అరవై", 7: "డెబ్బై", 8: "ఎనభై", 9: "తొంభై"}


def te_number(n: int) -> str:
    """Telugu words for 0 <= n < 1,000,000 (e.g. 110 -> నూట పది, 650 -> ఆరు వందల యాభై). num2words' Telugu reads
    100 as 'ఒకటి వంద' and 15 as 'పదునయిదు', which no newsreader says."""
    if n < 10:
        return TE_UNITS[n]
    if n < 20:
        return TE_TEENS[n - 10]
    if n < 100:
        t, u = divmod(n, 10)
        return TE_TENS[t] if not u else f"{TE_TENS[t]} {TE_UNITS[u]}"
    if n < 1000:
        h, r = divmod(n, 100)
        if not r:
            return "వంద" if h == 1 else f"{TE_UNITS[h]} వందలు"
        return f"{'నూట' if h == 1 else TE_UNITS[h] + ' వందల'} {te_number(r)}"
    k, r = divmod(n, 1000)
    head = "వెయ్యి" if k == 1 else f"{te_number(k)} వేల" if r else f"{te_number(k)} వేలు"
    return head if not r else f"{head} {te_number(r)}"


def say_numbers(text: str, lang: str) -> str:
    """Digits (with an optional decimal part) to words in Telugu or Tamil."""
    word = te_number if lang == "te" else ta_number
    point = "పాయింట్" if lang == "te" else "புள்ளி"

    def sub(m: re.Match) -> str:
        whole, frac = m.group(1).replace(",", ""), m.group(2)
        out = word(int(whole))
        if frac:
            out += f" {point} " + " ".join(word(int(d)) for d in frac)
        return f" {out} "
    return re.sub(r"(\d[\d,]*)(?:\.(\d+))?", sub, text)


UNITS = {"te": [(r"km/h|kmph|కి\.మీ\./గం", "కిలోమీటర్లు గంటకు"), (r"\bkm\b|కి\.మీ\.?", "కిలోమీటర్లు"), (r"\bhPa\b", "హెక్టోపాస్కల్"),
                (r"\bIMD\b", "ఐ ఎం డి"), (r"\bJTWC\b", "జె టి డబ్ల్యు సి"), (r"%", " శాతం")],
         "ta": [(r"km/h|kmph|கி\.மீ\./மணி", "கிலோமீட்டர் மணிக்கு"), (r"\bkm\b|கி\.மீ\.?", "கிலோமீட்டர்"), (r"\bhPa\b", "ஹெக்டோபாஸ்கல்"),
                (r"\bIMD\b", "ஐ எம் டி"), (r"\bJTWC\b", "ஜே டி டபிள்யூ சி"), (r"%", " சதவீதம்")]}


def normalise(text: str, lang: str) -> str:
    text = re.sub(r"(\d)\s*[-–]\s*(\d)", r"\1 " + ("నుంచి" if lang == "te" else "முதல்") + r" \2", text)   # 100-110 -> 100 to 110
    text = text.replace("°", " ")
    for rx, repl in UNITS.get(lang, []):
        text = re.sub(rx, repl, text)
    text = say_numbers(text, lang)
    text = re.sub(r"[A-Za-z]+", " ", text)            # anything still Latin is unreadable for these vocabularies
    return re.sub(r"\s+", " ", text).strip()


def _load(lang: str, device: str):
    if lang not in _CACHE:
        from transformers import AutoTokenizer, VitsModel

        path = MMS_DIR / MODELS[lang]
        _CACHE[lang] = (AutoTokenizer.from_pretrained(path), VitsModel.from_pretrained(path).to(device).eval())
    return _CACHE[lang]


def synthesize(text: str, language: str, device: str = "cuda", sentence_pause: float = 0.35,
               line_pause: float = 0.6) -> tuple[np.ndarray, int]:
    import torch

    lang = (language or "").lower().split("-")[0]
    if lang not in MODELS:
        raise ValueError(f"MMS-TTS has no voice for {language!r} (have: {', '.join(MODELS)})")
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    tok, model = _load(lang, device)
    rate = model.config.sampling_rate
    out: list[np.ndarray] = []
    for line in [l for l in text.splitlines() if l.strip()]:
        for sent in [s for s in re.split(r"(?<=[.!?।])\s+", line) if s.strip()]:
            spoken = normalise(sent, lang)
            if not spoken:
                continue
            torch.manual_seed(7)                              # same voice texture every time
            with torch.no_grad():
                wav = model(**tok(spoken, return_tensors="pt").to(device)).waveform[0].float().cpu().numpy()
            out += [wav, np.zeros(int(rate * sentence_pause), dtype=np.float32)]
        out.append(np.zeros(int(rate * line_pause), dtype=np.float32))
    if not out:
        raise ValueError("nothing to say")
    audio = np.concatenate(out)
    peak = float(np.abs(audio).max()) or 1.0
    return (audio / peak * 0.9).astype(np.float32), rate

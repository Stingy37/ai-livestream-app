"""Per-sentence TTS for beat scripts: every line is synthesised on its own, so the package knows exactly when each
sentence (and so each beat and each focus) starts and ends.

synthesize(script, lang, wav_path) -> beats timeline [{"visual", "start", "end", "lines": [{text, start, end, speaker, focus}]}]
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

import numpy as np

from models import tts_kokoro as tk

KOKORO = Path("/home/andyshi2/pre-models/Kokoro-82M")
RATE = 24000
VOICES = {"es": {"A": "ef_dora", "B": "em_alex"}, "ja": {"A": "jf_alpha", "B": "jm_kumo"}, "zh": {"A": "zf_xiaoxiao", "B": "zm_yunxi"}}
LANG_CODE = {"es": "e", "ja": "j", "zh": "z"}
SPEED = {"es": 1.05, "ja": 1.05, "zh": 1.0}
GAP_LINE, GAP_SPEAKER, GAP_BEAT, LEAD_IN, TAIL = 0.22, 0.38, 0.55, 0.15, 0.6
_lock = threading.Lock()


# English names read with Spanish spelling rules go wrong (Harris -> "Arris", Dallas -> "Dayas"): respell them the way
# Spanish-language US networks say them. Only whole words; the on-screen text keeps the real spelling.
_ES_SAY = {
    "Harris": "Járris", "Dallas": "Dálas", "Collin": "Cólin", "Bexar": "Béjar", "Hegar": "Jéigar", "Cornyn": "Córnin",
    "Paxton": "Pákston", "Talarico": "Talárico", "Cruz": "Crus",
    "Sullivan": "Sálivan", "Peltola": "Péltola", "Murkowski": "Murkóski", "Gross": "Gros",
    "Marshall": "Márshal", "Hamilton": "Jámilton", "Moran": "Morán", "Bollier": "Bolíer", "Johnson": "Yónson",
    "Sedgwick": "Séyuik", "Shawnee": "Shoní", "Douglas": "Dóglas", "Wyandotte": "Uáiandot", "Leavenworth": "Lévenuorz",
    "Collins": "Cólins", "Jackson": "Yákson", "King": "Kin", "Gideon": "Guídeon", "Cumberland": "Cámberland",
    "York": "Iork", "Penobscot": "Penóbscot", "Kennebec": "Kénebek", "Androscoggin": "Androscóguin", "Hancock": "Jáncok",
    "Husted": "Jústed", "Sherrod": "Shérod", "Brown": "Bráun", "Moreno": "Moreno", "Ryan": "Ráian", "Vance": "Vans",
    "Franklin": "Fránklin", "Cuyahoga": "Caiajóga", "Summit": "Sámit", "Montgomery": "Montgómeri", "Stark": "Stark",
    "El-Sayed": "El Saíd", "Abdul": "Abdul", "Rogers": "Róyers", "Mike": "Maik", "Peters": "Píters", "Slotkin": "Slótkin",
    "Elissa": "Elísa", "Gary": "Guéri", "James": "Yeims", "Wayne": "Uéin", "Oakland": "Óuklan", "Macomb": "Mácom",
    "Kent": "Kent", "Washtenaw": "Uáshtenau", "Genesee": "Yénesi",
    "Ken": "Ken", "Ted": "Ted", "Dan": "Dan", "Mary": "Méri", "Lisa": "Lísa", "Roger": "Róyer", "Adam": "Ádam",
    "Jerry": "Yérri", "Susan": "Súsan", "Troy": "Troi", "Angus": "Ángus", "Jon": "Yon", "Bernie": "Bérni", "John": "Yon",
    "Barbara": "Bárbara", "Sara": "Sára", "Tim": "Tim", "Trump": "Tramp", "Kamala": "Kámala", "Brad": "Brad",
    "Texas": "Téjas", "Kansas": "Kánsas", "Maine": "Méin", "Ohio": "Ojáio", "Michigan": "Míchigan", "Alaska": "Alaska",
}
_ES_RE = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, _ES_SAY), key=len, reverse=True)) + r")(?![\w-])")


def _say_es(t: str) -> str:
    t = _ES_RE.sub(lambda m: _ES_SAY[m.group(1)], t)
    t = re.sub(r"(\d+),(\d+)\s*%", r"\1 coma \2 por ciento", t)
    t = re.sub(r"(\d+)\s*%", r"\1 por ciento", t)
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", t)                    # 230.000 -> 230000
    t = re.sub(r"(\d+),(\d+)", r"\1 coma \2", t)                    # 1,23 millones
    t = re.sub(r"\bAP\b", "A P", t)
    t = t.replace("EE. UU.", "Estados Unidos").replace("EE.UU.", "Estados Unidos")
    return t


# readings the Japanese G2P gets wrong in this domain (checked phoneme by phoneme): 郡 -> こおり, 歳 -> とし,
# "54.8" -> a pause instead of てん
_JA_FIX = [("郡", "ぐん"), ("歳", "さい"), ("下院", "かいん"), ("上院", "じょういん"), ("第1希望", "だいいちきぼう"),
           ("中間選", "ちゅうかんせん"), ("無所属", "むしょぞく"), ("票差", "ひょうさ")]


_JA_HOUR = ["れい", "いち", "に", "さん", "よ", "ご", "ろく", "しち", "はち", "く", "じゅう", "じゅういち", "じゅうに", "じゅうさん",
            "じゅうよ", "じゅうご", "じゅうろく", "じゅうしち", "じゅうはち", "じゅうく", "にじゅう", "にじゅういち", "にじゅうに",
            "にじゅうさん", "にじゅうよ"]


def _say_ja(t: str) -> str:
    t = re.sub(r"(?<!\d)(\d{1,2})時(?!間)", lambda m: (_JA_HOUR[int(m.group(1))] + "じ") if int(m.group(1)) <= 24 else m.group(0), t)
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    t = t.replace("AP通信", "エーピー通信")
    t = re.sub(r"(\d+)\.(\d+)", r"\1点\2", t)
    for a, b in _JA_FIX:
        t = t.replace(a, b)
    return tk.normalise_ja(t).replace("\n", "")


def _say_zh(t: str) -> str:
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    return tk.normalise_zh(t).replace("\n", "")


SAY = {"es": _say_es, "ja": _say_ja, "zh": _say_zh}


def _pipe(lang: str):
    return tk._pipeline(KOKORO, "cuda", LANG_CODE[lang])


def _tts(text: str, lang: str, voice: str) -> np.ndarray:
    pipe = _pipe(lang)
    vp = str(tk.voice_path(KOKORO, voice))
    chunks = []
    with _lock:
        for _gs, _ps, audio in pipe(SAY[lang](text), voice=vp, speed=SPEED[lang], split_pattern=r"\n+"):
            if audio is None:
                continue
            arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
            chunks.append(arr.astype(np.float32))
    if not chunks:
        return np.zeros(int(0.3 * RATE), dtype=np.float32)
    a = np.concatenate(chunks)
    # trim leading/trailing near-silence so the timeline is tight
    idx = np.where(np.abs(a) > 0.01)[0]
    return a[max(0, idx[0] - 240): idx[-1] + 2400] if len(idx) else a


def synthesize(script: dict, lang: str, wav_path: Path) -> tuple[list[dict], float]:
    import soundfile as sf

    parts: list[np.ndarray] = [np.zeros(int(LEAD_IN * RATE), dtype=np.float32)]
    t = LEAD_IN
    beats, prev_spk = [], None
    for bi, b in enumerate(script["beats"]):
        if bi:
            parts.append(np.zeros(int(GAP_BEAT * RATE), dtype=np.float32))
            t += GAP_BEAT
        bstart = t
        lines = []
        for li, ln in enumerate(b["lines"]):
            spk = ln.get("speaker") if ln.get("speaker") in ("A", "B") else "A"
            if li:
                gap = GAP_SPEAKER if spk != prev_spk else GAP_LINE
                parts.append(np.zeros(int(gap * RATE), dtype=np.float32))
                t += gap
            a = _tts(ln["text"], lang, VOICES[lang][spk])
            parts.append(a)
            lines.append({"text": ln["text"], "start": round(t, 3), "end": round(t + len(a) / RATE, 3), "speaker": spk,
                          "focus": ln.get("focus")})
            t += len(a) / RATE
            prev_spk = spk
        beats.append({"visual": b["visual"], "start": round(bstart, 3), "end": round(t, 3), "lines": lines})
    parts.append(np.zeros(int(TAIL * RATE), dtype=np.float32))
    audio = np.concatenate(parts)
    # beats tile the whole clip: each runs until the next one starts
    for i in range(len(beats) - 1):
        beats[i]["end"] = beats[i + 1]["start"]
    if beats:
        beats[0]["start"] = 0.0
        beats[-1]["end"] = round(len(audio) / RATE, 3)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio * min(1.0, 0.92 / peak)
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = wav_path.with_suffix(".tmp.wav")
    sf.write(str(tmp), audio, RATE, subtype="PCM_16")
    tmp.replace(wav_path)
    return beats, round(len(audio) / RATE, 3)

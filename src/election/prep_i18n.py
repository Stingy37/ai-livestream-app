"""One-time localisation of the static election data (run before the night, re-runnable; results are cached).

    python -m election.prep_i18n            # from src/

Writes data/election/i18n.json:
  cards[ST][key][lang]  = {role, facts[3], positions[4]}   candidate cards (from races.json featured.*.candidates)
  units[ST][id][lang]   = {name, short}                     county / district names
  notes[ST][i][lang]    = str                               senators' notes

Translations come from the LLM with strict instructions (faithful, neutral, attribution verbs kept, nothing added),
then a deterministic check: every digit sequence of the source survives, the target script is right, and the
number of items is unchanged. A failed item is retried, then left in English (never invented).
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.lumen import get_pool  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "election"
OUT = DATA / "i18n.json"
LANGS = {"es": "Spanish (neutral Latin American news register)", "ja": "Japanese (concise NHK-style news text, plain form)",
         "zh": "Simplified Chinese (mainland/Singapore news register, 简体字)"}
SCRIPT = {"ja": re.compile(r"[぀-ヿ一-鿿]"), "zh": re.compile(r"[一-鿿]")}

SYSTEM = """You translate short factual texts about US election candidates for a strictly neutral news broadcast.
Rules: translate faithfully and completely; add nothing, drop nothing; keep every number, year and proper noun;
keep attribution exactly ("says", "supports", "opposes" -> the target language's neutral equivalents, e.g. 〜と主張している/〜を支持している, 表示/支持/反对, dice/apoya/se opone);
never add adjectives, evaluations or labels; keep quotation marks around quoted words; US place names in the
standard form used by that language's major news media (Japanese: katakana; Chinese: standard Xinhua transliteration).
Return only JSON."""


def _ask(user: str) -> dict:
    raw = get_pool().chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                          json_mode=True, max_tokens=4000, temperature=0.1)
    return json.loads(raw)


def _digits(s: str) -> list[str]:
    return sorted(re.findall(r"\d+", s.replace(",", "")))


_EN_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


def _en_values(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(thousand|million|billion|trillion)?", text):
        out.append(float(m.group(1).replace(",", "")) * _EN_MULT.get(m.group(2) or "", 1))
    return out


def _ok(src: list[str], dst: list[str], lang: str) -> bool:
    """Every figure of the source survives (by value: $1 billion = 10億ドル = 1.000 millones); small numbers may
    become dates or ordinals, and a spelled-out number word may become digits (sixth grade -> 6年生)."""
    from election.qc import numbers
    if len(src) != len(dst) or not all(isinstance(d, str) and d.strip() for d in dst):
        return False
    for s, d in zip(src, dst):
        if lang in SCRIPT and not SCRIPT[lang].search(d):
            return False
        tv = numbers(d.replace("$", " "), lang)
        for v in _en_values(s):
            if v <= 31:
                continue
            if not any(abs(v - x) <= max(0.5, v * 0.001) for x in tv):
                return False
        if any(x > 31 and not any(abs(x - v) <= max(0.5, x * 0.001) for v in _en_values(s)) for x in tv):
            return False
    return True


def translate_list(texts: list[str], lang: str, context: str) -> list[str] | None:
    user = (f"Target language: {LANGS[lang]}.\nContext: {context}\nTranslate each item. Return "
            f'{{"items": [...]}} with exactly {len(texts)} strings in the same order.\n\n'
            + json.dumps(texts, ensure_ascii=False))
    for _ in range(3):
        try:
            got = _ask(user).get("items")
        except Exception:  # noqa: BLE001
            continue
        if isinstance(got, list) and _ok(texts, got, lang):
            return [g.strip() for g in got]
    return None


def unit_names(names: list[str], lang: str, state: str, kind: str) -> dict[str, dict]:
    if kind == "house_district":
        out = {}
        for n in names:
            num = int(re.sub(r"\D", "", n))
            out[n] = {"es": {"name": f"Distrito {num}", "short": f"D{num}"}, "ja": {"name": f"第{num}選挙区", "short": f"{num}区"},
                      "zh": {"name": f"第{num}选区", "short": f"{num}区"}}[lang]
        return out
    if lang == "es":
        return {n: {"name": f"condado de {n}", "short": n} for n in names}
    suffix = {"ja": "郡", "zh": "县"}[lang]
    user = (f"Target language: {LANGS[lang]}. These are counties of the US state {state}. For each county give the "
            f"standard {'katakana' if lang == 'ja' else 'Chinese'} transliteration of the county name WITHOUT the word "
            f"for county (e.g. Harris -> {'ハリス' if lang == 'ja' else '哈里斯'}). Return {{\"names\": {{\"<English>\": \"<translit>\"}}}}.\n\n"
            + json.dumps(names, ensure_ascii=False))
    for _ in range(3):
        try:
            got = _ask(user).get("names") or {}
        except Exception:  # noqa: BLE001
            continue
        if all(isinstance(got.get(n), str) and SCRIPT[lang].search(got[n]) for n in names):
            return {n: {"name": got[n].strip() + suffix, "short": got[n].strip()} for n in names}
    return {n: {"name": n, "short": n} for n in names}


def main() -> int:
    races = json.loads((DATA / "races.json").read_text(encoding="utf-8"))
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out.setdefault("cards", {}); out.setdefault("units", {}); out.setdefault("notes", {})
    jobs = []
    for st, f in races["featured"].items():
        for c in f["candidates"]:
            for lang in LANGS:
                if out["cards"].get(st, {}).get(c["key"], {}).get(lang):
                    continue
                jobs.append(("card", st, c, lang))
        for lang in LANGS:
            if not out["units"].get(st, {}).get(lang):
                jobs.append(("units", st, None, lang))
            if not out["notes"].get(st, {}).get(lang):
                jobs.append(("notes", st, None, lang))

    def run(job):
        kind, st, c, lang = job
        f = races["featured"][st]
        if kind == "card":
            role = c.get("current_office") or (c.get("prior_offices") or [""])[0] or ""
            src = [role] + [b["text"] for b in c.get("background", [])] + [p["text"] for p in c.get("positions", [])]
            got = translate_list(src, lang, f"Candidate {c['name']} ({c['party']}) for US Senate in {f['state_name']['en']}.")
            if not got:
                return kind, st, c, lang, None
            nb = len(c.get("background", []))
            return kind, st, c, lang, {"role": got[0], "facts": got[1:1 + nb], "positions": got[1 + nb:]}
        if kind == "units":
            base = json.loads((DATA / "baseline" / f"{st}.json").read_text(encoding="utf-8"))
            names = [u["name"] for u in base["units"]]
            m = unit_names(names, lang, f["state_name"]["en"], base.get("unit_type", "county"))
            return kind, st, None, lang, {u["id"]: m[u["name"]] for u in base["units"]}
        notes = [s.get("note") or "" for s in f["senators"]]
        idx = [i for i, n in enumerate(notes) if n]
        got = translate_list([notes[i] for i in idx], lang, f"Notes about current US senators from {f['state_name']['en']}.") if idx else []
        res = [""] * len(notes)
        for i, g in zip(idx, got or []):
            res[i] = g
        return kind, st, None, lang, res

    with ThreadPoolExecutor(8) as ex:
        for kind, st, c, lang, val in ex.map(run, jobs):
            if val is None:
                print(f"FAILED {kind} {st} {c['key'] if c else ''} {lang}", flush=True)
                continue
            if kind == "card":
                out["cards"].setdefault(st, {}).setdefault(c["key"], {})[lang] = val
            else:
                out[kind].setdefault(st, {})[lang] = val
            print(f"ok {kind} {st} {c['key'] if c else ''} {lang}", flush=True)
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

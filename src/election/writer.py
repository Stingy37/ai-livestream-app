"""Beat scripts for one scene: prompt -> deepseek (Lumen) -> QC -> rewrite with feedback (<= 3 rounds).

write_scene(kind, key, lang, snapshot, previous=None) -> (script, report)
script = {"beats": [{"visual", "lines": [{"speaker": "A"|"B", "text", "focus"}]}]}
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from election import facts as FX
from election import qc
from models.lumen import get_pool

log = logging.getLogger(__name__)

LANG_STYLE = {
    "es": """Write in neutral Latin American broadcast Spanish (no regionalisms), for viewers in the US and Latin America.
Numbers: digits; decimals with a comma ("52,1 %"); ALWAYS round vote counts in speech, the exact count is on screen
("unos 1,84 millones de votos", "unos 230.000 votos"). Keep each line under 130 characters. Times: "las 9 de la noche, hora del Este". Say "la agencia AP" for the Associated Press.
Party labels: "el republicano X", "la demócrata X", "Partido Republicano", "Partido Demócrata".""",
    "ja": """Write natural Japanese for NHK-style election coverage (です・ます調), for viewers in Japan watching on Wednesday daytime.
People: surname + 氏 after the first full mention (e.g. ケン・パクストン氏 → パクストン氏). Places: the given katakana names.
Numbers: Arabic digits; ALWAYS round vote counts to 万 in speech ("約184万票"; the exact count is on screen); percentages "52.1%". Times: give US Eastern time AND Japan time
as written in the facts ("米東部時間午後9時、日本時間4日午前11時"). The Associated Press is "AP通信". Never use 開票率.
Party: 共和党, 民主党, 無所属.""",
    "zh": """Write natural Mandarin in Simplified Chinese (简体字) for a news broadcast for overseas Chinese viewers.
People: the given Chinese names; places: the given names. Numbers: Arabic digits; ALWAYS round vote counts to 万 in speech ("约184万票"; the exact count is on screen);
percentages "52.1%". Times: US Eastern time AND Beijing time as written in the facts. The Associated Press is "美联社".
Never use 开票率. Party: 共和党, 民主党, 无党派. Never use 蓝营/绿营.""",
}

SYSTEM = """You write the narration for a live US election-results broadcast with two presenters:
A = the anchor at the desk, B = the analyst at the touchscreen map. They talk to each other and to the audience like
the best network election-night teams: brisk, clear, energetic, explaining what the numbers on screen mean. The
broadcast is strictly neutral and every sentence is spoken over a specific graphic.

OUTPUT: JSON {"beats": [{"visual": "<visual id>", "lines": [{"speaker": "A"|"B", "text": "<one spoken sentence>",
"focus": "<id or null>"}]}]}

HARD RULES (a QC program rejects scripts that break them):
1. ALIGNMENT: a beat's lines may only talk about what that beat's visual shows: use ONLY the facts listed under that
   visual id. Every number you say must appear in that visual's facts (rounding is fine). If you want to say something
   from another visual, put it in a beat with that visual.
2. FOCUS: when a line is about one county/district, candidate or senator shown on the graphic, set "focus" to its
   [focus id] from the facts, and name it in that line. The graphic zooms or highlights it while the line plays. Do
   not name a county without focusing it on st_counties / st_votes_left.
3. Cover the visuals in exactly the order given, one beat each (st_intro first), 2-6 lines per beat. You do NOT have to
   use every fact: choose the most informative ones and stay inside the length.
4. NEUTRAL: no adjectives or labels for candidates, parties, places or turnout; no predictions ("will win", "expected",
   "favoured", "on track", "momentum", "must-win", "path to victory"); no advocacy; no voting instructions. Results
   verbs only: leads / is ahead / trails / is behind by N. Counties described with numbers only.
5. CALLS: never say or imply anyone won tonight. Only if the facts contain an AP declaration, relay it exactly as given,
   naming AP in that sentence.
6. VOTES LEFT: only as "votes counted so far equal X% of the 2022 midterm total". Never "X% of the vote is in", never
   "N votes remain".
7. POLLS OPEN: if the facts say polls are still open, give no results and never say the polls have closed.
8. CANDIDATES: equal treatment. On st_candidates give each candidate the same number of lines (±1), alternate who goes
   first, attribute every position ("X says ...", "X supports ..."), only facts from the cards.
9. Plain spoken sentences: no brackets, no lists, no markup, no stage directions, no abbreviations except AP; each line
   one sentence of at most {max_line} characters. Trends are unknown: never say a lead is growing or shrinking.
10. Natural, varied, engaging: open with a hook from the facts (what is at stake in this state tonight, in facts),
    let B explain the map, let A ask B short questions, signpost ("let's look at the counties"), compare tonight with
    2024 and 2022 using the numbers given. Never repeat a sentence; do not reuse the previous opening.

{lang_style}"""


# streams read by ONE presenter (Japanese: viewers preferred the single male voice; Kokoro has one ja male voice)
SOLO: set[str] = set()                 # e.g. {"ja"} to make a stream single-anchor
SOLO_NOTE = """

SINGLE PRESENTER for this stream (overrides the two-presenter setup above): one male anchor reads everything.
Set "speaker": "A" on every line. No dialogue: no questions to a co-host, no names or roles of other presenters, no
"thank you" hand-offs. Keep the energy with signposting to the audience ("ではテキサス州の郡別の状況を見てみましょう")."""


def _visuals(kind: str, snap: dict) -> tuple[list[str], str]:
    if kind == "national":
        return FX.NATIONAL_ORDER, "national"
    ph = FX.state_phase(snap)
    return FX.STATE_ORDER[ph], ph


def build_prompt(kind: str, lang: str, snap: dict, facts: dict, order: list[str], phase: str, previous: dict | None) -> list[dict]:
    lo, hi = qc.TARGET[kind][lang]
    unit = "characters" if lang != "es" else "characters including spaces"
    sysmsg = SYSTEM.replace("{max_line}", str(qc.MAX_LINE[lang])).replace("{lang_style}", LANG_STYLE[lang])
    if lang in SOLO:
        sysmsg += SOLO_NOTE
    head = (f"SCENE: {'the national Senate picture' if kind == 'national' else snap['state_name'] + ' — ' + snap['race_label']}\n"
            f"PHASE: {phase}\nLENGTH: {lo}-{hi} {unit} in total (about {2 if kind == 'state' else 1.5} minutes spoken; "
            f"roughly {'18-24' if kind == 'state' else '12-16'} lines). Stay inside this range.\n"
            f"VISUALS IN ORDER: {order}\n")
    body = "FACTS BY VISUAL:\n" + "\n".join(f"[{v}]\n" + "\n".join(f"- {x}" for x in facts.get(v, [])) for v in order)
    prev = ""
    if previous:
        first = next((ln["text"] for b in previous.get("beats", []) for ln in b.get("lines", [])), "")
        prev = f"\nPREVIOUS VERSION'S OPENING (do not reuse it or its structure): {first}\n"
    return [{"role": "system", "content": sysmsg}, {"role": "user", "content": head + body + prev}]


def _parse(raw: str) -> dict:
    try:
        d = json.loads(raw)
    except ValueError:
        s, e = raw.find("{"), raw.rfind("}")
        d = json.loads(raw[s:e + 1]) if s >= 0 < e else {}
    for b in d.get("beats", []) if isinstance(d, dict) else []:
        for ln in b.get("lines", []) or []:
            if ln.get("focus") in ("null", "None", ""):
                ln["focus"] = None
            if ln.get("focus") is not None:
                ln["focus"] = str(ln["focus"])
    return d if isinstance(d, dict) else {}


def write_scene(kind: str, key: str, lang: str, snap: dict, previous: dict | None = None,
                max_rounds: int = 3, now: datetime | None = None) -> tuple[dict | None, dict]:
    now = now or datetime.now(timezone.utc)
    facts = FX.national_facts(snap, lang, now) if kind == "national" else FX.state_facts(snap, lang, now)
    order, phase = _visuals(kind, snap)
    ctx = {"lang": lang, "kind": kind, "phase": phase, "facts": facts, "snapshot": snap, "allowed_visuals": order, "order": order}
    msgs = build_prompt(kind, lang, snap, facts, order, phase, previous)
    best, best_n, report = None, 10**9, {"rounds": [], "phase": phase}
    reviewed = False
    for rnd in range(max_rounds):
        t0 = time.time()
        try:
            raw = get_pool().chat(msgs, json_mode=True, max_tokens=6000, temperature=0.7 if rnd == 0 else 0.4)
            script = _parse(raw)
        except Exception as error:  # noqa: BLE001
            report["rounds"].append({"error": str(error)[:300]})
            continue
        hard, review = qc.check(script, ctx, use_llm=not reviewed)
        if not hard and review:
            reviewed = True
        report["rounds"].append({"hard": hard, "review": review, "s": round(time.time() - t0, 1)})
        fatal = [h for h in hard if not h.startswith(("Too short", "Too long")) and "; split it" not in h]
        n = len(fatal) * 10 + (len(hard) - len(fatal)) * 2 + len(review)
        if n < best_n and not any("must be JSON" in h for h in hard):
            best, best_n = script, n
        if not hard and not review:
            break
        fb = hard[:12] + review[:6]
        msgs = msgs[:2] + [{"role": "assistant", "content": json.dumps(script, ensure_ascii=False)},
                           {"role": "user", "content": "Fix these problems and return the whole corrected JSON:\n- " + "\n- ".join(fb)}]
    ok = best is not None and best_n < 10            # no hard problem left (review notes alone don't block)
    report.update(accepted=ok, score=best_n)
    return (best if ok else None), report

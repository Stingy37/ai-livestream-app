"""Text sections of desk.json (warnings, impact status and chips, headlines, ticker) via the Lumen LLM.

The model only *selects and condenses*; it never supplies facts. Every item it returns must carry
an exact quote (a contiguous substring, whitespace/quote-style insensitive) of one of the numbered
sources it was shown, and every number in the item must appear in that quote. Items that fail
either check are dropped in code. When nothing valid remains for a country, the caller writes a
plain "nothing reported" line instead of keeping old text.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 6000          # per source shown to the model (the quote check runs on the full text)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
# words a viewer acts on: they may only appear when the quoted source uses them too
_CRITICAL = ("landfall", "evacuat", "suspend", "suspension", "signal", "warning", "storm surge", "flood", "closed", "cancel")
_ABSENCE = re.compile(r"\b(no|not|none|nil|without|never)\b|n't")


@dataclass
class Source:
    sid: str                     # "S1", "S2", ... as shown to the model
    agency: str
    url: str
    issued: str                  # ISO UTC or ""
    text: str
    kind: str = "agency"         # agency | scraped


@dataclass
class TextResult:
    items: dict[str, Any] = field(default_factory=dict)
    dropped: list[dict] = field(default_factory=list)
    calls: int = 0


def norm(s: str) -> str:
    s = (s or "").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").replace("–", "-").replace("—", "-")
    s = s.replace(" ", " ")
    return " ".join(s.split()).lower()


def numbers(s: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(s or "")}


def check_item(item: dict, sources: dict[str, Source], text_fields: tuple[str, ...]) -> str | None:
    """None if the item is grounded, else the reason it is not."""
    src = sources.get(str(item.get("source", "")).strip())
    quote = str(item.get("quote", "")).strip()
    if src is None:
        return "unknown source"
    if len(quote) < 12:
        return "quote too short"
    if norm(quote) not in norm(src.text):
        return "quote not in source"
    qnums = numbers(quote)
    nq = norm(quote)
    for f in text_fields:
        nt = norm(str(item.get(f, "")))
        # "no warnings", "not expected", "none": an absence claim needs a negation in the quote too
        if _ABSENCE.search(nt) and not _ABSENCE.search(nq):
            return f"absence claim in {f} not supported by the quote"
        for term in _CRITICAL:
            if term in nt and term not in nq:
                return f"'{term}' in {f} not in the quote"
        missing = numbers(str(item.get(f, ""))) - qnums
        if missing:
            return f"number(s) {sorted(missing)} in {f} not in quote"
    return None


def _render_sources(sources: list[Source]) -> str:
    parts = []
    for s in sources:
        body = s.text if len(s.text) <= MAX_SOURCE_CHARS else s.text[:MAX_SOURCE_CHARS] + "\n[...]"
        parts.append(f"[{s.sid}] {s.agency} ({s.kind}, issued {s.issued or 'time not stated'}) {s.url}\n{body}")
    return "\n\n".join(parts)


RULES = (
    "Rules: use ONLY facts written in the sources below. Never invent or infer warnings, wind signals, evacuation "
    "orders, suspensions, figures, times or place names. Every item must include \"source\" (the [S#] id) and "
    "\"quote\": a sentence or phrase copied EXACTLY, character for character, from that source, that states the "
    "item's facts. Every number you write must appear in your quote. Prefer the official agency sources over news "
    "sites. Never claim that something is absent (no warnings, no impacts) unless a source says so in your quote. "
    "If the sources say nothing for a field, return null or an empty list for it. Return ONLY one JSON object."
)

COUNTRY_PROMPT = """You prepare one column of a live typhoon TV graphic about {storm} for {country} ({agency} is the national agency).
{rules}

JSON shape:
{{
 "level": "hot" | "watch" | "none",   // hot: warnings or wind signals in effect for land areas of {country} now; watch: they are forecast or possible; none: neither
 "status": {{"text": "<= 70 characters, the single most important status for {country}", "source": "S#", "quote": "..."}} | null,
 "warning": {{"text": "<= 170 characters: what {agency} warns or expects, for whom and when", "source": "S#", "quote": "..."}} | null,
 "chips": [{{"icon": "rain" | "wave" | "wind" | "clock", "label": "<= 24 characters", "value": "<= 48 characters", "source": "S#", "quote": "..."}}],   // up to 3 concrete hazards or timings
 "ticker": [{{"text": "<= 140 characters, one fact", "source": "S#", "quote": "..."}}]   // up to 3
}}

Sources:
{sources}
"""

HEADLINE_PROMPT = """You write the rotating lower-third headlines of a live typhoon TV broadcast about {storm}.
{rules}

JSON shape:
{{"headlines": [{{"main": "<= 60 characters", "sub": "<= 110 characters, starts with the agency name and a colon", "tag": "PHILIPPINES, TAIWAN, JAPAN or FORECAST", "source": "S#", "quote": "..."}}]}}   // up to 4, most decision-relevant first, one per tag; impacts and warnings, not the current wind numbers (shown elsewhere)

Sources:
{sources}
"""


def _ask(ask: Callable[[str, str], str], prompt: str) -> dict | None:
    from scraper.prompts import extract_json

    try:
        reply = ask("You are a careful broadcast editor who only reports what official sources say.", prompt)
    except Exception as e:  # noqa: BLE001
        log.warning("desk text LLM call failed: %s", e)
        return None
    data = extract_json(reply)
    return data if isinstance(data, dict) else None


def _clip(s: Any, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def country_text(ask, storm: str, country: str, agency: str, sources: list[Source]) -> TextResult:
    res = TextResult()
    if not sources:
        return res
    by_id = {s.sid: s for s in sources}
    data = _ask(ask, COUNTRY_PROMPT.format(storm=storm, country=country, agency=agency, rules=RULES,
                                          sources=_render_sources(sources)))
    res.calls = 1
    if not data:
        return res

    def keep(item, fields, name):
        if not isinstance(item, dict):
            return None
        why = check_item(item, by_id, fields)
        if why:
            res.dropped.append({"section": name, "reason": why, "item": item})
            return None
        src = by_id[item["source"]]
        out = {**{f: _clip(item.get(f), 200) for f in fields}, "source_url": src.url, "agency": src.agency,
               "quote": " ".join(str(item["quote"]).split())}
        if name == "chip":
            icon = str(item.get("icon", "")).lower()
            out["icon"] = icon if icon in ("rain", "wave", "wind", "clock") else "wind"
        return out

    res.items["status"] = keep(data.get("status"), ("text",), "status")
    res.items["warning"] = keep(data.get("warning"), ("text",), "warning")
    res.items["chips"] = [c for c in (keep(c, ("label", "value"), "chip") for c in (data.get("chips") or [])[:3]) if c]
    res.items["ticker"] = [t for t in (keep(t, ("text",), "ticker") for t in (data.get("ticker") or [])[:3]) if t]
    lvl = str(data.get("level", "none")).lower()
    # a level other than none needs a grounded warning or status to stand on
    res.items["level"] = lvl if lvl in ("hot", "watch") and (res.items["warning"] or res.items["status"]) else "none"
    return res


def headline_text(ask, storm: str, sources: list[Source], skip_tags: tuple[str, ...] = ("LIVE TRACK",)) -> TextResult:
    res = TextResult()
    if not sources:
        return res
    by_id = {s.sid: s for s in sources}
    data = _ask(ask, HEADLINE_PROMPT.format(storm=storm, rules=RULES, sources=_render_sources(sources)))
    res.calls = 1
    out, tags = [], {}
    for h in (data or {}).get("headlines") or []:
        if not isinstance(h, dict):
            continue
        why = check_item(h, by_id, ("main", "sub"))
        if why:
            res.dropped.append({"section": "headline", "reason": why, "item": h})
            continue
        src = by_id[h["source"]]
        tag = _clip(str(h.get("tag") or src.agency).upper(), 16)
        if tag in skip_tags or tags.get(tag, 0) >= 1:     # one headline per tag; the caller's own ones win
            res.dropped.append({"section": "headline", "reason": f"duplicate tag {tag}", "item": h})
            continue
        tags[tag] = tags.get(tag, 0) + 1
        # the sub line is attributed to the source the quote really came from, whatever the model wrote
        sub = re.sub(r"^\s*[A-Za-z][\w .&'-]{0,30}:\s*", "", str(h.get("sub") or ""))
        out.append({"main": _clip(h.get("main"), 70), "sub": _clip(f"{src.agency}: {sub}", 130), "tag": tag,
                    "source_url": src.url, "quote": " ".join(str(h["quote"]).split())})
    res.items["headlines"] = out[:4]
    return res


def dump_dropped(results: list[TextResult]) -> list[dict]:
    out = []
    for r in results:
        for d in r.dropped:
            out.append({"section": d["section"], "reason": d["reason"],
                        "item": json.loads(json.dumps(d["item"], ensure_ascii=False, default=str))})
    return out

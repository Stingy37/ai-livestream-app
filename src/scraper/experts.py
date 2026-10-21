"""The three experts of the scraper graph (internal to the Web Scraper team).

They run only when the verify node's baseline fails. Each looks at the gathered sources and tells
the ReAct search node what to look for next. None of them may change the documents or the verify
output: their whole output is notes, gaps, unreported figures and search suggestions.

    typhoon expert ..... position, intensity, forecast track and timing
    emergency expert ... rain, temperature/weather, surge, signals, evacuations, suspensions
    citizen expert ..... is the result clear and actionable? (flags wording and missing actions, adds no facts)
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from contracts import ScrapedDocument

from scraper.prompts import (CITIZEN_EXPERT_SYSTEM, CITIZEN_USER, EMERGENCY_EXPERT_SYSTEM, EXPERT_USER,
                             TYPHOON_EXPERT_SYSTEM, as_str_list, extract_json)

log = logging.getLogger(__name__)

EXPERT_DOC_CAP = int(os.environ.get("SCRAPE_EXPERT_DOC_CHARS", "1800"))
EXPERT_TOTAL_CAP = int(os.environ.get("SCRAPE_LLM_TOTAL_CHARS", "14000"))
MAX_SUGGESTIONS = 4

AskFn = Callable[[str, str], str]

EXPERTS = (
    ("typhoon", TYPHOON_EXPERT_SYSTEM),
    ("emergency", EMERGENCY_EXPERT_SYSTEM),
    ("citizen", CITIZEN_EXPERT_SYSTEM),
)


def docs_digest(docs: list[ScrapedDocument], per_doc: int, total: int) -> str:
    """Numbered digest of the documents for a prompt, each cut to ``per_doc`` chars, all to ``total``."""
    parts, used = [], 0
    for i, d in enumerate(docs, start=1):
        room = min(per_doc, total - used)
        if room <= 200:
            parts.append(f"[{i}] (and {len(docs) - i + 1} more documents not shown)")
            break
        head = f"[{i}] {d.source_name} — {d.title} ({d.published_at.isoformat() if d.published_at else 'no date'}; {d.url})\n"
        body = d.main_text[:room].strip()
        parts.append(head + body)
        used += len(head) + len(body)
    return "\n\n".join(parts)


def run_experts(docs: list[ScrapedDocument], scene_title: str, topic: str, now_iso: str, checklist: list[str],
                missing: list[str], flags: list[str], ask: AskFn, max_threads: int = 3) -> dict[str, Any]:
    """Run all three experts (concurrently) and collect their feedback for the next search round."""
    digest = docs_digest(docs, EXPERT_DOC_CAP, EXPERT_TOTAL_CAP)
    common = dict(title=scene_title, topic=topic, now=now_iso, cap=EXPERT_DOC_CAP, docs=digest)

    def one(name: str, system: str) -> tuple[str, dict[str, Any]]:
        if name == "citizen":
            user = CITIZEN_USER.format(**common)
        else:
            user = EXPERT_USER.format(checklist=", ".join(checklist) or "n/a", missing=", ".join(missing) or "none",
                                      flags="; ".join(flags) or "none", **common)
        try:
            data = extract_json(ask(system, user))
        except Exception as exc:  # noqa: BLE001 - one expert failing must not stop the round
            log.warning("%s expert failed: %s", name, exc)
            data = None
        return name, normalise_expert(name, data)

    with ThreadPoolExecutor(max_workers=max(1, min(max_threads, len(EXPERTS))), thread_name_prefix="expert") as pool:
        results = dict(pool.map(lambda e: one(*e), EXPERTS))
    suggestions: list[str] = []
    for name, _ in EXPERTS:
        for s in results[name].get("search_suggestions", []):
            if s not in suggestions:
                suggestions.append(s)
    return {"experts": results, "search_suggestions": suggestions[: MAX_SUGGESTIONS * 2]}


def normalise_expert(name: str, data: Any) -> dict[str, Any]:
    """Coerce an expert reply into its fixed shape (lists of strings); missing fields become empty."""
    d = data if isinstance(data, dict) else {}
    if name == "citizen":
        return {"unclear_wording": as_str_list(d.get("unclear_wording"), 12),
                "missing_actions": as_str_list(d.get("missing_actions"), 12),
                "search_suggestions": as_str_list(d.get("search_suggestions"), 3)}
    return {"notes": as_str_list(d.get("notes"), 12), "gaps": as_str_list(d.get("gaps"), 12),
            "unreported_figures": as_str_list(d.get("unreported_figures"), 12),
            "search_suggestions": as_str_list(d.get("search_suggestions"), MAX_SUGGESTIONS)}

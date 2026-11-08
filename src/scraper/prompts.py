"""Prompts for the agentic scraper and a lenient JSON reader for model replies.

Every prompt says the same two things: nothing may be invented, and everything the model
reports must be traceable to the supplied source text. The verify node and the experts never
produce facts of their own; they only quote, flag and point out gaps.
"""

from __future__ import annotations

import json
import re
from typing import Any

NO_INVENTION = (
    "Rules: never invent figures, place names, timestamps, evacuation orders, warnings or agency names. "
    "Only report what the supplied source text literally says, and quote it. If something is not in the "
    "sources, say it is not reported. Return ONLY valid JSON, no prose, no markdown fences."
)

# ---- search node (ReAct) ---------------------------------------------------------------------
PLAN_SYSTEM = (
    "You are the research planner of a typhoon news desk. You decide what to search for next so that a "
    "broadcast segment can be written from official, recent sources. Think step by step: write a short "
    "Thought, then the Action as JSON. " + NO_INVENTION
)
PLAN_USER = (
    "Scene: {title}\nWhat the segment must cover: {topic}\nToday (UTC): {now}\n"
    "Web search allowed: {web_search}\n"
    "Already gathered ({n_docs} documents):\n{gathered}\n"
    "Feedback from the previous round (gaps to close, if any):\n{feedback}\n"
    "Candidate links on already fetched pages that could be followed (same site only):\n{links}\n\n"
    "Propose the next actions. Prefer official agencies and the most recent bulletins, matching the agency to "
    "the area (PAGASA / NDRRMC for the Philippines, CWA for Taiwan, JMA for Japan, HKO for Hong Kong, JTWC for "
    "1-minute winds); do not put one agency's name in every query; use the storm name and local names; vary the "
    "queries so each targets a different missing item; at most {max_queries} queries and at most {max_links} links.\n"
    'Reply as: Thought: <one or two sentences>\nAction: {{"queries": ["..."], "follow_urls": ["..."], '
    '"time_range": "day" | "week" | null}}'
)

SUFFICIENT_SYSTEM = (
    "You are the editor of a typhoon news desk judging whether the gathered sources are enough to write "
    "one broadcast segment. Be concrete about what is missing. " + NO_INVENTION
)
SUFFICIENT_USER = (
    "Scene: {title}\nWhat the segment must cover: {topic}\nToday (UTC): {now}\n\n"
    "Gathered sources (each cut to its first {cap} characters):\n{docs}\n\n"
    'Reply as JSON: {{"sufficient": true or false, "missing": ["what is still missing, one item each"], '
    '"covered": ["what is already covered, briefly"]}}'
)

# ---- verify node -----------------------------------------------------------------------------
CLAIMS_SYSTEM = (
    "You extract factual claims about a tropical cyclone from one source document. A claim is a quantity or "
    "statement an agency reports: position, maximum sustained winds, gusts, central pressure, movement "
    "direction and speed, forecast position, forecast intensity, wind signal / warning level, rainfall, storm "
    "surge, evacuation order, class or work suspension, landfall time or place. " + NO_INVENTION
)
CLAIMS_USER = (
    "Source: {source_name} — {title}\nURL: {url}\nPublished: {published}\nText (first {cap} characters):\n"
    "\"\"\"\n{text}\n\"\"\"\n\n"
    "List up to {max_claims} claims. 'quote' must be an EXACT substring of the text above (copy it verbatim, "
    "20 to 200 characters). 'agency' is the agency the text attributes the claim to, or the source itself. "
    "'quantity_type' is one of: position, sustained_wind, gust, pressure, movement, forecast_position, "
    "forecast_intensity, wind_signal, warning, rainfall, surge, evacuation, suspension, landfall, other. "
    "'value' and 'unit' are the figure as written (strings), empty when not a number. 'time' is the analysis, "
    "valid or issue time written in the text for that claim, as written, or empty.\n"
    'Reply as JSON: {{"claims": [{{"quote": "...", "agency": "...", "quantity_type": "...", "value": "...", '
    '"unit": "...", "time": "..."}}]}}'
)

CONFLICT_SYSTEM = (
    "You compare claims about the same tropical cyclone quantity from different agencies and say whether they "
    "materially conflict. Differences explained by issue time, averaging period (1-minute versus 10-minute "
    "winds), units (kt, km/h, m/s), rounding or a different forecast hour are NOT conflicts. " + NO_INVENTION
)
CONFLICT_USER = (
    "Quantity: {quantity_type}\nCandidate pairs (each from two different agencies):\n{pairs}\n\n"
    "For each pair decide whether A and B materially conflict about the SAME thing at the SAME time. A different "
    "issue time, forecast hour, averaging period, unit, rounding, or a different place or quantity means NO conflict. "
    "State both values in the reason.\n"
    'Reply as JSON: {{"conflicts": [{{"pair": <pair number>, "reason": "one short sentence with both values"}}]}} '
    "with an empty list when nothing conflicts."
)

CHECKLIST_SYSTEM = (
    "You turn a broadcast segment description into a short coverage checklist: the kinds of facts the "
    "sources must contain before the segment can be written. " + NO_INVENTION
)
CHECKLIST_USER = (
    "Scene: {title}\nWhat the segment must cover: {topic}\n\n"
    "Pick 3 to 7 items from this vocabulary that this segment needs: position, sustained_wind, gust, pressure, "
    "movement, forecast_position, forecast_intensity, wind_signal, warning, rainfall, surge, evacuation, "
    "suspension, landfall, agency_attribution, official_channels. For a sign-off or station identification "
    "segment that cites no figures, pick only agency_attribution and official_channels.\n"
    'Reply as JSON: {{"checklist": ["..."]}}'
)

# ---- experts ---------------------------------------------------------------------------------
EXPERT_COMMON = (
    "You review the gathered sources for one broadcast segment and tell the research agent what to search for "
    "next. You never add facts: you may only quote the sources, point out gaps, and list figures that have not "
    "been reported. " + NO_INVENTION
)
TYPHOON_EXPERT_SYSTEM = (
    "You are a tropical cyclone specialist (position, intensity, forecast track and timing, agency differences "
    "such as 1-minute versus 10-minute winds). " + EXPERT_COMMON
)
EMERGENCY_EXPERT_SYSTEM = (
    "You are an emergency management specialist (rainfall, temperature and weather conditions, storm surge, "
    "wind signals, evacuations, class/work/transport suspensions, shelters, affected areas). " + EXPERT_COMMON
)
CITIZEN_EXPERT_SYSTEM = (
    "You are an ordinary resident in the storm's path reading the gathered information. You judge only whether "
    "it is clear and actionable for someone like you: what is unclear, and what action or decision is still "
    "missing (when, where, what to do). You add NO facts and propose only what to look for. " + NO_INVENTION
)
EXPERT_USER = (
    "Scene: {title}\nWhat the segment must cover: {topic}\nToday (UTC): {now}\n"
    "Coverage checklist: {checklist}\nChecklist items not yet covered: {missing}\n"
    "Verified flags: {flags}\n\n"
    "Gathered sources (each cut to its first {cap} characters):\n{docs}\n\n"
    'Reply as JSON: {{"notes": ["short observations, each quoting a source"], "gaps": ["information missing for '
    'this segment"], "unreported_figures": ["figures the segment needs that no source reports"], '
    '"search_suggestions": ["concrete search queries or official pages to fetch, at most 4"]}}'
)
CITIZEN_USER = (
    "Scene: {title}\nWhat the segment must cover: {topic}\nToday (UTC): {now}\n\n"
    "Gathered sources (each cut to its first {cap} characters):\n{docs}\n\n"
    'Reply as JSON: {{"unclear_wording": ["phrases or figures a resident would not understand, quoted"], '
    '"missing_actions": ["decisions a resident still cannot make from this information"], '
    '"search_suggestions": ["what to look for so the segment becomes actionable, at most 3"]}}'
)


# ---- lenient JSON reader ---------------------------------------------------------------------
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def extract_json(reply: str | None) -> Any | None:
    """The first JSON object (or array) in a model reply, or None.

    Tolerates <think> blocks, markdown fences, prose before and after, and trailing commas.
    """
    if not reply:
        return None
    text = _THINK_RE.sub("", reply)
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                c = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                    continue
                if c == '"':
                    in_str = True
                elif c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i + 1]
                        parsed = _loads(candidate)
                        if parsed is not None:
                            return parsed
                        break
            start = text.find(opener, start + 1)
    return None


def _loads(s: str) -> Any | None:
    try:
        return json.loads(s)
    except ValueError:
        pass
    try:  # trailing commas
        return json.loads(re.sub(r",\s*([}\]])", r"\1", s))
    except ValueError:
        return None


def as_str_list(x: Any, limit: int | None = None) -> list[str]:
    """Coerce a model field into a list of non-empty strings."""
    if x is None:
        return []
    if isinstance(x, str):
        items = [x]
    elif isinstance(x, list):
        items = [str(i.get("text", i.get("query", i))) if isinstance(i, dict) else str(i) for i in x]
    else:
        items = [str(x)]
    out = [i.strip() for i in items if i and str(i).strip()]
    return out[:limit] if limit else out

"""The verify node of the scraper graph (internal to the Web Scraper team).

For every gathered document the model lists the claims it makes (as exact quotes). Claims whose
quote is not a substring of the document text are dropped, so nothing the model made up can
survive. The node then flags only two things:

    * agency conflicts: the same quantity for the same storm reported with materially different
      values by different agencies (judged by the model on the quoted claims; unit/averaging/time
      differences are not conflicts);
    * stale data: a claim time or the document's published time older than STALE_HOURS before
      the fetch.

It never adds facts, evacuation orders, figures or place names. The baseline gate then decides
whether the pool is good enough for the segment: every checklist item covered by a non-stale
document and no unresolved agency conflict (``BaselineRule``).
"""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from contracts import ScrapedDocument

from scraper.prompts import (CHECKLIST_SYSTEM, CHECKLIST_USER, CLAIMS_SYSTEM, CLAIMS_USER, CONFLICT_SYSTEM,
                             CONFLICT_USER, as_str_list, extract_json)

log = logging.getLogger(__name__)

STALE_HOURS = float(os.environ.get("STALE_HOURS", "6"))
DOC_CAP = int(os.environ.get("SCRAPE_LLM_DOC_CHARS", "6000"))      # document text shown to the model per call
MAX_CLAIMS = int(os.environ.get("SCRAPE_MAX_CLAIMS", "25"))
CLAIMS_MAX_TOKENS = int(os.environ.get("SCRAPE_CLAIMS_MAX_TOKENS", "3000"))   # a claims list is long; never cut it short
CONFLICT_MIN_AGENCIES = 2

QUANTITY_TYPES = ("position", "sustained_wind", "gust", "pressure", "movement", "forecast_position", "forecast_intensity",
                  "wind_signal", "warning", "rainfall", "surge", "evacuation", "suspension", "landfall", "other")
CHECKLIST_VOCAB = QUANTITY_TYPES[:-1] + ("agency_attribution", "official_channels")

AskFn = Callable[[str, str], str]   # (system_prompt, user_text) -> reply


@dataclass
class Claim:
    doc_url: str
    source_name: str
    quote: str
    agency: str
    quantity_type: str
    value: str = ""
    unit: str = ""
    time: str = ""
    stale: bool = False
    age_hours: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class VerifyResult:
    claims: list[Claim] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)      # {quantity_type, a, b, reason} with claim dicts
    stale_docs: dict[str, dict[str, Any]] = field(default_factory=dict)  # url -> {stale, age_hours, reason}
    dropped_claims: int = 0
    llm_calls: int = 0

    def flags_for(self, url: str) -> dict[str, Any]:
        """What goes into document.metadata['verify']."""
        st = self.stale_docs.get(url, {"stale": False, "age_hours": None})
        conflicts = [c for c in self.conflicts if url in (c["a"]["doc_url"], c["b"]["doc_url"])]
        return {"stale": bool(st.get("stale")), "age_hours": st.get("age_hours"), "stale_reason": st.get("reason", ""),
                "conflicts": [{"quantity_type": c["quantity_type"], "reason": c["reason"],
                               "this": c["a"]["quote"] if c["a"]["doc_url"] == url else c["b"]["quote"],
                               "other": c["b"]["quote"] if c["a"]["doc_url"] == url else c["a"]["quote"],
                               "other_agency": c["b"]["agency"] if c["a"]["doc_url"] == url else c["a"]["agency"]}
                              for c in conflicts],
                "claims": sum(1 for c in self.claims if c.doc_url == url)}

    def to_dict(self) -> dict[str, Any]:
        return {"claims": [c.to_dict() for c in self.claims], "conflicts": self.conflicts, "stale_docs": self.stale_docs,
                "dropped_claims": self.dropped_claims, "llm_calls": self.llm_calls}


# ---------------------------------------------------------------------------------------------
# staleness
# ---------------------------------------------------------------------------------------------
def age_hours(published_at: datetime | None, fetched_at: datetime | None) -> float | None:
    if published_at is None:
        return None
    fetched = fetched_at or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return max(0.0, (fetched - published_at).total_seconds() / 3600.0)


def is_stale(published_at: datetime | None, fetched_at: datetime | None, stale_hours: float = STALE_HOURS) -> tuple[bool, float | None, str]:
    """(stale, age_hours, reason). A date without a time of day (midnight) is judged by calendar day:
    a page dated today is not stale, so a bulletin page that only prints its date is not thrown out."""
    age = age_hours(published_at, fetched_at)
    if age is None:
        return False, None, "no published time on the page"
    if age > 24 * 365:
        return False, None, "published date on the page is over a year old: treated as unknown (likely a parsing artefact)"
    assert published_at is not None
    date_only = published_at.hour == 0 and published_at.minute == 0 and published_at.second == 0
    if date_only:
        fetched = (fetched_at or datetime.now(timezone.utc))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        cutoff_date = (fetched.timestamp() - stale_hours * 3600)
        stale = published_at.date() < datetime.fromtimestamp(cutoff_date, tz=timezone.utc).date()
        return stale, age, "date only on the page" + (", before the stale cutoff day" if stale else "")
    stale = age > stale_hours
    return stale, age, f"published {age:.1f} h before fetch" + (f" (> {stale_hours:g} h)" if stale else "")


_TIME_PATTERNS = [
    (re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::\d{2})?Z?"), "%Y-%m-%dT%H:%M"),
]


def claim_time_utc(raw: str, reference: datetime) -> datetime | None:
    """Best-effort parse of a claim's own time string; only ISO-like forms are trusted (others -> None)."""
    if not raw:
        return None
    m = _TIME_PATTERNS[0][0].search(raw)
    if not m:
        return None
    try:
        dt = datetime.strptime(f"{m.group(1)}T{m.group(2)}:{m.group(3)}", "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if "+09:00" in raw or "JST" in raw.upper():
        from datetime import timedelta

        dt = dt - timedelta(hours=9)
    elif "+08:00" in raw or "PHT" in raw.upper() or "PST" in raw.upper():
        from datetime import timedelta

        dt = dt - timedelta(hours=8)
    return dt


# ---------------------------------------------------------------------------------------------
# claims
# ---------------------------------------------------------------------------------------------
def extract_claims(doc: ScrapedDocument, ask: AskFn, cap: int = DOC_CAP, max_claims: int = MAX_CLAIMS) -> tuple[list[Claim], int]:
    """Claims of one document, keeping only those whose quote is an exact substring. (claims, dropped)."""
    text = doc.main_text[:cap]
    user = CLAIMS_USER.format(source_name=doc.source_name, title=doc.title, url=doc.url,
                              published=doc.published_at.isoformat() if doc.published_at else "not stated",
                              cap=cap, text=text, max_claims=max_claims)
    reply = ask_with(ask, CLAIMS_SYSTEM, user, max_tokens=CLAIMS_MAX_TOKENS)
    items = _claims_list(reply)
    if items is None:
        # unreadable or cut-off reply: ask once more for fewer claims, then salvage whatever objects are complete
        reply = ask_with(ask, CLAIMS_SYSTEM, user.replace(f"List up to {max_claims} claims", "List up to 10 claims"),
                         max_tokens=CLAIMS_MAX_TOKENS)
        items = _claims_list(reply)
        if items is None:
            items = salvage_claim_objects(reply)
    if not isinstance(items, list):
        return [], 0
    claims, dropped = [], 0
    for it in items[:max_claims]:
        if not isinstance(it, dict):
            dropped += 1
            continue
        quote = _norm(str(it.get("quote", "")))
        if not quote or not quote_in_text(quote, doc.main_text):
            dropped += 1
            continue
        qt = str(it.get("quantity_type", "other")).strip().lower()
        if qt not in QUANTITY_TYPES:
            qt = "other"
        claims.append(Claim(doc_url=doc.url, source_name=doc.source_name, quote=quote,
                            agency=canonical_agency(str(it.get("agency") or ""), doc.source_name), quantity_type=qt,
                            value=str(it.get("value") or ""), unit=str(it.get("unit") or ""), time=str(it.get("time") or "")))
    return claims, dropped


def _claims_list(reply: str) -> list | None:
    data = extract_json(reply)
    if isinstance(data, dict) and isinstance(data.get("claims"), list):
        return data["claims"]
    if isinstance(data, list):
        return data
    return None


_OBJ_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def salvage_claim_objects(reply: str | None) -> list[dict[str, Any]]:
    """Complete {...} objects from a reply whose JSON was cut off mid-array (flat claim objects only)."""
    out = []
    for m in _OBJ_RE.finditer(reply or ""):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(obj, dict) and "quote" in obj:
            out.append(obj)
    return out


def ask_with(ask: AskFn, system: str, user: str, **kw: Any) -> str:
    """Call ``ask`` with extra keyword arguments (max_tokens) when it accepts them, else without."""
    try:
        return ask(system, user, **kw)
    except TypeError:
        return ask(system, user)


_AGENCY_ALIASES = [
    ("pagasa", "PAGASA"), ("philippine atmospheric", "PAGASA"), ("jma", "JMA"), ("japan meteorological", "JMA"),
    ("jtwc", "JTWC"), ("joint typhoon", "JTWC"), ("cwa", "CWA"), ("central weather", "CWA"), ("cwb", "CWA"),
    ("hko", "HKO"), ("hong kong observatory", "HKO"), ("nhc", "NHC"), ("national hurricane", "NHC"),
    ("ndrrmc", "NDRRMC"), ("kma", "KMA"), ("korea meteorological", "KMA"), ("nws", "NWS"), ("noaa", "NOAA"),
]


def canonical_agency(agency: str, fallback: str) -> str:
    """One name per agency, whatever wording the model copied from the page."""
    low = (agency or "").lower()
    for needle, name in _AGENCY_ALIASES:
        if needle in low:
            return name
    return agency.strip() or fallback


def quote_in_text(quote: str, text: str) -> bool:
    """Exact substring check that tolerates whitespace differences and surrounding quotes only."""
    q = _norm(quote).strip(" \"'“”‘’")
    return bool(q) and q in _norm(text)


_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip()


# ---------------------------------------------------------------------------------------------
# conflicts
# ---------------------------------------------------------------------------------------------
def find_conflicts(claims: list[Claim], ask: AskFn) -> tuple[list[dict[str, Any]], int]:
    """Agency conflicts per quantity type. Deterministic gating first (``candidate_pairs``), then the model
    judges only the pairs that survive, on the quoted claims alone."""
    by_type: dict[str, list[Claim]] = {}
    for c in claims:
        if c.quantity_type == "other":
            continue
        by_type.setdefault(c.quantity_type, []).append(c)
    conflicts, calls = [], 0
    for qt, group in by_type.items():
        pairs = candidate_pairs(qt, group)
        if not pairs:
            continue
        pairs = pairs[:MAX_PAIRS_PER_TYPE]
        listing = "\n".join(f"Pair {i + 1}:\n  A [{a.agency}] {a.quote} (value: {a.value} {a.unit}; time: {a.time or 'n/a'})\n"
                            f"  B [{b.agency}] {b.quote} (value: {b.value} {b.unit}; time: {b.time or 'n/a'})" for i, (a, b) in enumerate(pairs))
        calls += 1
        data = extract_json(ask(CONFLICT_SYSTEM, CONFLICT_USER.format(quantity_type=qt, pairs=listing)))
        items = data.get("conflicts") if isinstance(data, dict) else None
        for it in items or []:
            try:
                k = int(it["pair"]) - 1
            except (KeyError, TypeError, ValueError):
                continue
            if not 0 <= k < len(pairs):
                continue
            a, b = pairs[k]
            conflicts.append({"quantity_type": qt, "a": a.to_dict(), "b": b.to_dict(), "reason": str(it.get("reason", ""))[:300]})
    return conflicts, calls


MAX_PAIRS_PER_TYPE = int(os.environ.get("SCRAPE_MAX_CONFLICT_PAIRS", "12"))
TIME_WINDOW_H = float(os.environ.get("SCRAPE_CONFLICT_TIME_WINDOW_H", "3"))   # claims further apart in time are not compared
ONE_MINUTE_AGENCIES = {"jtwc", "nhc", "nws", "noaa"}          # 1-minute winds; everyone else reports 10-minute winds
TIMED_ONLY = {"position", "forecast_position", "forecast_intensity", "movement"}   # meaningless to compare across times
NUMERIC_TYPES = {"sustained_wind", "gust", "pressure", "rainfall", "surge", "wind_signal", "forecast_intensity"}
_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_WIND_TO_KMH = {"kt": 1.852, "kts": 1.852, "knots": 1.852, "knot": 1.852, "km/h": 1.0, "kph": 1.0, "kmh": 1.0, "m/s": 3.6,
                "mps": 3.6, "mph": 1.609}


def candidate_pairs(qt: str, group: list[Claim]) -> list[tuple[Claim, Claim]]:
    """Pairs of claims from DIFFERENT agencies that could really conflict:
    * both timed and within TIME_WINDOW_H of each other, or at most one timed (positions, forecasts and
      movement need both times, or they are skipped: a storm moves);
    * winds: not a 1-minute (JTWC) versus 10-minute (JMA/PAGASA/CWA/HKO) pair, that difference is expected;
    * numbers in the same unit family that differ by less than the rounding tolerance are not conflicts."""
    out = []
    for i, a in enumerate(group):
        for b in group[i + 1:]:
            if a.agency.lower() == b.agency.lower() or a.doc_url == b.doc_url and a.quote == b.quote:
                continue
            ta, tb = claim_time_utc(a.time, datetime.now(timezone.utc)), claim_time_utc(b.time, datetime.now(timezone.utc))
            if ta is not None and tb is not None:
                if abs((ta - tb).total_seconds()) > TIME_WINDOW_H * 3600:
                    continue
            elif qt in TIMED_ONLY:
                continue
            if qt in ("sustained_wind", "gust", "forecast_intensity"):
                one_a, one_b = a.agency.lower() in ONE_MINUTE_AGENCIES, b.agency.lower() in ONE_MINUTE_AGENCIES
                if one_a != one_b:
                    continue
            if qt in NUMERIC_TYPES and (_number(a) is None or _number(b) is None):
                continue   # "Magnitude Unit: kts" is not a figure
            if numbers_agree(qt, a, b):
                continue
            out.append((a, b))
    return out


def numbers_agree(qt: str, a: Claim, b: Claim) -> bool:
    """True when both claims carry a number in a comparable unit and the numbers are within tolerance."""
    va, vb = _number(a), _number(b)
    if va is None or vb is None:
        return False
    ua, ub = _unit(a), _unit(b)
    if qt in ("sustained_wind", "gust", "forecast_intensity", "movement"):
        if ua in _WIND_TO_KMH and ub in _WIND_TO_KMH:
            va, vb = va * _WIND_TO_KMH[ua], vb * _WIND_TO_KMH[ub]
        elif ua != ub:
            return False
        return abs(va - vb) <= 0.10 * max(abs(va), abs(vb), 1.0)
    if qt == "pressure":
        return ua == ub and abs(va - vb) <= 5.0
    if qt in ("rainfall", "surge"):
        return ua == ub and abs(va - vb) <= 0.15 * max(abs(va), abs(vb), 1.0)
    if qt == "wind_signal":
        return va == vb
    return False


def _number(c: Claim) -> float | None:
    m = _NUM_RE.search(c.value or "") or _NUM_RE.search(c.quote or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _unit(c: Claim) -> str:
    u = (c.unit or "").strip().lower()
    if u:
        return u
    q = (c.quote or "").lower()
    for cand in ("km/h", "kph", "m/s", "kt", "knots", "mph", "hpa", "mb", "mm"):
        if cand in q:
            return cand
    return ""


# ---------------------------------------------------------------------------------------------
# the node
# ---------------------------------------------------------------------------------------------
def verify_documents(docs: list[ScrapedDocument], ask: AskFn, stale_hours: float = STALE_HOURS,
                     previous: VerifyResult | None = None, max_threads: int = 6) -> VerifyResult:
    """Run claim extraction (once per document; results of earlier rounds are reused), staleness and conflicts."""
    result = VerifyResult()
    done = {c.doc_url for c in previous.claims} if previous else set()
    reuse = [c for c in (previous.claims if previous else []) if c.doc_url in {d.url for d in docs}]
    result.claims.extend(reuse)
    result.dropped_claims = previous.dropped_claims if previous else 0
    todo = []
    for doc in docs:
        stale, age, reason = is_stale(doc.published_at, doc.fetched_at, stale_hours)
        result.stale_docs[doc.url] = {"stale": stale, "age_hours": None if age is None else round(age, 2), "reason": reason}
        if doc.url not in done:
            todo.append(doc)

    def one(doc: ScrapedDocument) -> tuple[list[Claim], int]:
        try:
            return extract_claims(doc, ask)
        except Exception as exc:  # noqa: BLE001 - a failed call must not kill the scene
            log.warning("claim extraction failed for %s: %s", doc.url, exc)
            return [], 0

    # one model call per document, run concurrently (vLLM / Lumen batch them)
    if todo:
        with ThreadPoolExecutor(max_workers=max(1, min(max_threads, len(todo))), thread_name_prefix="claims") as pool:
            for claims, dropped in pool.map(one, todo):
                result.llm_calls += 1
                result.dropped_claims += dropped
                result.claims.extend(claims)
    # claim-level staleness from the claim's own time, else the document's
    for c in result.claims:
        doc = next((d for d in docs if d.url == c.doc_url), None)
        fetched = doc.fetched_at if doc else None
        ct = claim_time_utc(c.time, fetched or datetime.now(timezone.utc))
        if ct is not None:
            c.age_hours = age_hours(ct, fetched)
            c.stale = (c.age_hours or 0) > stale_hours
        else:
            st = result.stale_docs.get(c.doc_url, {})
            c.stale, c.age_hours = bool(st.get("stale")), st.get("age_hours")
    try:
        result.conflicts, calls = find_conflicts(result.claims, ask)
        result.llm_calls += calls
    except Exception as exc:  # noqa: BLE001
        log.warning("conflict check failed: %s", exc)
    return result


# ---------------------------------------------------------------------------------------------
# baseline gate
# ---------------------------------------------------------------------------------------------
@dataclass
class BaselineRule:
    """The pass rule, explicit and configurable:
    every checklist item is covered by at least one NON-STALE claim of that type (``agency_attribution``
    = at least one claim with an agency; ``official_channels`` = at least one official agency document),
    and the number of unresolved agency conflicts is at most ``max_conflicts``. A non-empty pool with
    ``min_docs`` documents is also required."""

    max_conflicts: int = int(os.environ.get("SCRAPE_BASELINE_MAX_CONFLICTS", "0"))
    min_docs: int = int(os.environ.get("SCRAPE_BASELINE_MIN_DOCS", "1"))
    min_coverage: float = float(os.environ.get("SCRAPE_BASELINE_MIN_COVERAGE", "1.0"))   # share of checklist items


OFFICIAL_AGENCIES = {"JMA", "JTWC", "PAGASA", "CWA", "HKO", "NHC", "NWS", "NOAA", "KMA", "NDRRMC", "NCHMF"}


def derive_checklist(title: str, topic: str, ask: AskFn) -> list[str]:
    data = extract_json(ask(CHECKLIST_SYSTEM, CHECKLIST_USER.format(title=title, topic=topic)))
    items = as_str_list(data.get("checklist") if isinstance(data, dict) else data)
    cleaned = [i.strip().lower().replace(" ", "_") for i in items]
    cleaned = [i for i in cleaned if i in CHECKLIST_VOCAB]
    return list(dict.fromkeys(cleaned)) or ["position", "sustained_wind", "movement", "agency_attribution"]


def baseline(checklist: list[str], docs: list[ScrapedDocument], verify: VerifyResult,
             rule: BaselineRule | None = None) -> dict[str, Any]:
    rule = rule or BaselineRule()
    fresh = [c for c in verify.claims if not c.stale]
    covered, missing = [], []
    for item in checklist:
        if item == "agency_attribution":
            ok = any(c.agency for c in fresh)
        elif item == "official_channels":
            ok = any(d.source_name in OFFICIAL_AGENCIES and not verify.stale_docs.get(d.url, {}).get("stale") for d in docs)
        else:
            ok = any(c.quantity_type == item for c in fresh)
        (covered if ok else missing).append(item)
    coverage = len(covered) / len(checklist) if checklist else 1.0
    passed = (len(docs) >= rule.min_docs and coverage >= rule.min_coverage and len(verify.conflicts) <= rule.max_conflicts)
    return {"passed": passed, "checklist": checklist, "covered": covered, "missing": missing, "coverage": round(coverage, 3),
            "conflicts": len(verify.conflicts), "docs": len(docs), "stale_docs": sum(1 for v in verify.stale_docs.values() if v["stale"]),
            "rule": {"max_conflicts": rule.max_conflicts, "min_docs": rule.min_docs, "min_coverage": rule.min_coverage}}

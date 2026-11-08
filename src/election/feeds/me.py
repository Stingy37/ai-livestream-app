"""Maine: Secretary of State tabulations (Excel, by municipality), aggregated to the 16 counties.

Maine has no statewide election-night results feed. Municipal clerks report to the Secretary of State, who posts
tabulations as .xlsx files on the year's results page (https://www.maine.gov/sos/elections-voting/election-results-data/
election-results-2026) in the days after the election ("1st choice results reported by the municipalities" for
ranked-choice contests, and "FINAL" files at certification, within 20 days). U.S. Senate general elections in Maine use
ranked-choice voting, so the town file carries first-choice votes; any RCV rounds are run centrally in Augusta.

The sheet layout (2024 "US Senator FINAL.xlsx", same office and format since 2018):

    COUNTY | MUNICIPALITY | <Last, First> ... | BLANK | TBC      <- header (TBC = total ballots cast)
           |              | <residence town> ...                <- row 2
           |              | <party> ...                         <- row 3
    AND    | Auburn       | 309 | 1288 | ...                    <- one row per municipality
           | AND Total    | ...                                 <- county subtotal (skipped, recomputed)
           | STATE UOCAVA | ...                                 <- overseas/military: statewide only
           | STATEWIDE TOTALS | ...                             <- used as the official statewide total

Towns are kept under the extra ``towns`` key (allowed by the spec); ``precincts`` is null (not published).

Access: www.maine.gov is behind CloudFront and, as of 2026-11-02, answers this client (honest UA) with "403 Request
blocked" on every path, robots.txt included; the adapter reports that as SourceBlocked.

Config (env): ME_RESULTS_PAGE, ME_XLSX_URL (skip discovery), ME_LINK (regex for the Senate file link text/href).
"""

from __future__ import annotations

import io
import re
from urllib.parse import urljoin

import requests

from . import common as C

STATE = "ME"
SOURCE = "Maine Secretary of State"
CONFIG = {
    "results_page": C.env("ME_RESULTS_PAGE", "https://www.maine.gov/sos/elections-voting/election-results-data/"
                                             "election-results-2026"),
    "xlsx_url": C.env("ME_XLSX_URL"),
    "link": C.env("ME_LINK", r"(U\.?\s*S\.?|United\s+States)[\s%20-]*Senat"),
}
COUNTY_CODES = {"AND": "Androscoggin", "ARO": "Aroostook", "CUM": "Cumberland", "FRA": "Franklin", "HAN": "Hancock",
                "KEN": "Kennebec", "KNO": "Knox", "LIN": "Lincoln", "OXF": "Oxford", "PEN": "Penobscot",
                "PIS": "Piscataquis", "SAG": "Sagadahoc", "SOM": "Somerset", "WAL": "Waldo", "WAS": "Washington",
                "YOR": "York"}
_NON_CAND = {"BLANK", "BLANKS", "TBC", "TOTAL", "TOTAL VOTES", "OVERVOTES", "OVER VOTES", "UNDERVOTES",
             "TOTAL BALLOTS CAST", "EXHAUSTED"}
_WRITEIN = re.compile(r"^(write[\s-]*ins?|others?|scattering)$", re.I)


def _cell(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def parse_xlsx(content: bytes, *, source_url: str = "", source_updated_at: str | None = None) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = next((w for w in wb.worksheets if re.search(r"SENAT", w.title, re.I)), wb.worksheets[0])
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    hi = next((i for i, r in enumerate(rows[:20]) if _cell(r[0]).upper() == "COUNTY" and
               _cell(r[1] if len(r) > 1 else "").upper().startswith("MUNICIPAL")), None)
    if hi is None:
        raise C.ParseError("ME: no COUNTY | MUNICIPALITY header row")
    header = [_cell(x) for x in rows[hi]]
    cols: list[tuple[int, str]] = []
    for j, h in enumerate(header[2:], start=2):
        if not h:
            continue
        if h.upper() in _NON_CAND:
            continue
        cols.append((j, h))
    if not cols:
        raise C.ParseError("ME: no candidate columns")
    party_row = None
    for r in rows[hi + 1:hi + 4]:
        vals = [_cell(r[j]) for j, _ in cols]
        if not _cell(r[0]) and any(re.search(r"(Republican|Democratic|Independent|Libertarian|Green)", v, re.I)
                                   for v in vals):
            party_row = vals
            break
    cands, col_key = [], {}
    for n, (j, h) in enumerate(cols):
        if _WRITEIN.match(h):
            col_key[j] = C.WRITEIN_KEY
            continue
        cands.append({"name": C.display_name(h), "source": h, "col": j, "order": n,
                      "party": C.norm_party(party_row[n]) if party_row else "OTH"})
    tmp = [{"name": c["source"], "order": c["order"]} for c in cands]
    C.assign_keys(tmp)
    for c, t in zip(cands, tmp):
        c["key"] = t["key"]
        col_key[c["col"]] = c["key"]
    if C.WRITEIN_KEY in col_key.values():
        cands.append({"key": C.WRITEIN_KEY, "name": "Write-ins", "party": "OTH", "order": 10**6})
    keys = [c["key"] for c in cands]

    def votes_of(r) -> dict[str, int]:
        v = {k: 0 for k in keys}
        for j, k in col_key.items():
            v[k] += C.to_int(r[j] if j < len(r) else 0)
        return v

    towns, counties, extra_sw, official_sw = [], {}, {k: 0 for k in keys}, None
    seen: dict[str, int] = {}
    for r in rows[hi + 1:]:
        if not r or all(x is None or _cell(x) == "" for x in r):
            continue
        code, town = _cell(r[0]).upper(), _cell(r[1] if len(r) > 1 else "")
        if re.fullmatch(r"STATEWIDE TOTALS?", town, re.I):
            official_sw = votes_of(r)
            continue
        if re.search(r"\bTotal$", town, re.I) or (not code and not town):
            continue
        if code in COUNTY_CODES:
            fips = C.county_fips("ME", COUNTY_CODES[code])
            v = votes_of(r)
            slug = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
            tid = f"{fips}-{slug}"
            seen[tid] = seen.get(tid, 0) + 1
            if seen[tid] > 1:
                tid = f"{tid}-{seen[tid]}"
            towns.append({"id": tid, "name": town, "county": fips, "votes": v, "total": sum(v.values())})
            cv = counties.setdefault(fips, {k: 0 for k in keys})
            for k in keys:
                cv[k] += v[k]
        elif re.search(r"UOCAVA|OVERSEAS|MILITARY", town, re.I) or not code:
            v = votes_of(r)
            for k in keys:
                extra_sw[k] += v[k]
        else:
            raise C.ParseError(f"ME: unknown county code {code!r} (row {town!r})")
    if len(counties) != 16:
        raise C.ParseError(f"ME: {len(counties)} counties in the file, expected 16")
    summed = {k: sum(cv[k] for cv in counties.values()) + extra_sw[k] for k in keys}
    if official_sw is not None and official_sw != summed:
        raise C.ParseError(f"ME: STATEWIDE TOTALS {official_sw} != towns + UOCAVA {summed}")
    for c in cands:
        c.pop("source", None), c.pop("col", None)
    units = [{"id": f, "name": C.county_name(f, "ME"), "votes": v, "precincts": None} for f, v in counties.items()]
    return C.build_result(state=STATE, unit_type="county", source=SOURCE, source_url=source_url,
                          source_updated_at=source_updated_at, candidates=cands, units=units,
                          statewide_votes=summed, statewide_precincts=None,
                          extra={"towns": sorted(towns, key=lambda t: t["id"])})


def discover(html: str, page_url: str, link_re: str | None = None) -> list[str]:
    """Senate .xlsx links on the results page; general-election files first (party-primary files last)."""
    import lxml.html
    link_re = link_re or CONFIG["link"]
    doc = lxml.html.fromstring(html)
    hits = []
    for a in doc.xpath("//a[@href]"):
        href = urljoin(page_url, a.get("href"))
        label = a.text_content() + " " + href.replace("-20", " ").replace("%20", " ")
        if href.lower().endswith((".xlsx", ".xls")) and re.search(link_re, label, re.I):
            primary = bool(re.search(r"\b(Dem|Rep|Green|Lib)\b", label, re.I))
            first_choice = bool(re.search(r"1st|first", label, re.I))
            hits.append((primary, not first_choice, href))
    return [h for _, _, h in sorted(set(hits))]


def fetch(session: requests.Session, *, xlsx_url: str | None = None) -> dict:
    url = xlsx_url or CONFIG["xlsx_url"]
    if not url:
        page = C.get(session, CONFIG["results_page"])
        links = [u for u in discover(page.text, CONFIG["results_page"])
                 if not re.search(r"\b(Dem|Rep|Green|Lib)\b", u.replace("-20", " ").replace("%20", " "), re.I)]
        if not links:
            raise C.NotPublished(f"ME: no U.S. Senate general tabulation linked on {CONFIG['results_page']} yet")
        url = links[0]
    f = C.get(session, url)
    return parse_xlsx(f.content, source_url=url, source_updated_at=f.last_modified)

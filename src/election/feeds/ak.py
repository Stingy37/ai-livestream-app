"""Alaska: Division of Elections election-night results (precinct CSV + summary PDF).

Alaska publishes election-night results as files on www.elections.alaska.gov (the live files are served from S3 under
/enr<YY>/results/ and later archived under /results/<YY><TYPE>/):

    GA_ENR_Precinct_State_of_Alaska.csv   one row per precinct x contest x candidate (ES&S "GA ENR" export)
    ElectionSummaryReportRPT.pdf          statewide summary with "Precincts Reported: X of Y" per contest

The CSV is the machine-readable source. Precinct ids "NN-xxx" carry the state house district (HD) number; the
non-geographic rows "District N - Absentee / Early Voting / Question" belong to HD N; "HD99 Fed Overseas Absentee"
counts statewide only. Units are therefore AK-HD01..AK-HD40, and the statewide total includes HD99.

U.S. Senate general elections use ranked-choice voting: the election-night numbers are first-choice votes; the RCV
tabulation is run by the Division after the count closes (about 15 days later). ``Reporting_flag`` is 0 on every row of
the archived files, so precincts are taken from the summary PDF (statewide) and per-HD only if the CSV flags are used.

The server sends the wrong TLS intermediate; certs/globalsign_gcc_r46_ov_tls_ca_2025.pem (GlobalSign GCC R46 OV TLS
CA 2025, chains to GlobalSign Root R46 in certifi) is added to the trust store. Verification stays on.

Config (env): AK_RESULTS_PAGE, AK_SECTION (regex of the results-page heading, default "2026 General Election"),
AK_CSV_URL / AK_PDF_URL (skip discovery), AK_RACE (contest title regex).
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from urllib.parse import urljoin

import requests

from . import common as C

STATE = "AK"
SOURCE = "Alaska Division of Elections"
BASE = "https://www.elections.alaska.gov"
EXTRA_CA = "globalsign_gcc_r46_ov_tls_ca_2025.pem"
CONFIG = {
    "results_page": C.env("AK_RESULTS_PAGE", BASE + "/election-results/"),
    "section": C.env("AK_SECTION", r"2026 General Election"),
    "csv_url": C.env("AK_CSV_URL"),
    "pdf_url": C.env("AK_PDF_URL"),
    "default_csv": BASE + "/enr26/results/GA_ENR_Precinct_State_of_Alaska.csv",
    "default_pdf": BASE + "/enr26/results/ElectionSummaryReportRPT.pdf",
    "race": C.env("AK_RACE", r"^U\.?\s*S\.?\s*Senator\b"),
    "title": C.env("AK_TITLE", r"2026 GENERAL ELECTION"),
}
PARTY = {"REP": "REP", "DEM": "DEM", "LIB": "LIB", "GRN": "GRN", "NON": "IND", "UND": "IND", "NOM": "IND"}
KEY_OVERRIDES = {"Sullivan, Dan S.": "sullivan", "Sullivan, Daniel J. Jr.": "sullivan_jr"}

_HD_PCT = re.compile(r"^(\d{2})-\d{3}$")
_HD_AGG = re.compile(r"^District\s+(\d{1,2})\s*-", re.I)


def unit_of(row: dict) -> str | None:
    """'AK-HD01'.. for a CSV row, or None for statewide-only rows (HD99 overseas)."""
    m = _HD_PCT.match(row.get("Pct_Id", "").strip())
    if m:
        n = int(m.group(1))
    else:
        m = _HD_AGG.match(row.get("Precinct_name", "").strip())
        if not m:
            return None
        n = int(m.group(1))
    return f"AK-HD{n:02d}" if 1 <= n <= 40 else None


def is_writein(row: dict) -> bool:
    return row.get("Candidate_Type", "").strip().upper() == "W" or bool(
        re.search(r"write[\s-]*in", row.get("candidate_name", ""), re.I))


def parse_summary_text(text: str, race_re: str | None = None) -> dict:
    """Title, timestamp and the race's 'Precincts Reported: X of Y' from the summary PDF text."""
    race_re = race_re or CONFIG["race"]
    out: dict = {"title": None, "status": None, "timestamp": None, "precincts": None}
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)", text[:400])
    if m:
        out["timestamp"] = C.local_to_iso(m.group(1), ["%m/%d/%Y %I:%M:%S %p"], "America/Anchorage")
    m = re.search(r"^\s*(\d{4}\s+[A-Z][A-Z ]*ELECTION)\s*$", text, re.M)
    out["title"] = m.group(1).strip() if m else None
    m = re.search(r"^\s*((?:UN)?OFFICIAL RESULTS)\s*$", text, re.M)
    out["status"] = m.group(1) if m else None
    lines = text.splitlines()
    pr = re.compile(r"Precincts Reported:\s*([\d,]+)\s+of\s+([\d,]+)")
    for i, line in enumerate(lines):
        if re.search(race_re, line.strip(), re.I):
            # pdfplumber puts the contest's line just after its title; the desk extractor just before it
            for near in lines[i + 1:i + 4] + lines[max(0, i - 3):i][::-1]:
                m = pr.search(near)
                if m:
                    out["precincts"] = {"reporting": C.to_int(m.group(1)), "total": C.to_int(m.group(2))}
                    break
            break
    return out


def pdf_text(content: bytes, pages: int = 1) -> str:
    """Text of the first ``pages`` pages: pdfplumber when installed, else the project's dependency-free extractor."""
    try:
        import pdfplumber
    except ImportError:
        from desk.pdftext import pdf_text as plain
        return plain(content)
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:pages])


def parse_csv(text: str, *, race_re: str | None = None, summary: dict | None = None,
              source_url: str = "", source_updated_at: str | None = None) -> dict:
    """Live results dict from the precinct CSV text (+ optional parsed summary for precincts/timestamp)."""
    race_re = race_re or CONFIG["race"]
    rows = [r for r in csv.DictReader(io.StringIO(text.lstrip("﻿")))
            if re.search(race_re, (r.get("Contest_title") or "").strip(), re.I)]
    if not rows:
        raise C.ParseError(f"AK: no rows for contest {race_re!r}")
    titles = {r["Contest_title"].strip() for r in rows}
    if len(titles) != 1:
        raise C.ParseError(f"AK: several contests match {race_re!r}: {sorted(titles)}")

    cands: dict[str, dict] = {}
    has_writein = False
    for r in rows:
        if is_writein(r):
            has_writein = True
            continue
        cid = r["candidate_id"].strip()
        if cid not in cands:
            raw = r["candidate_name"].strip()
            cands[cid] = {"source_name": raw, "name": C.display_name(raw), "party": PARTY.get(
                r.get("Party_Code", "").strip().upper(), "OTH"), "order": C.to_int(r.get("cand_seq_nbr"))}
    clist = list(cands.values())
    tmp = [dict(name=c["source_name"], order=c["order"]) for c in clist]     # keys from the "Last, First" form
    C.assign_keys(tmp, KEY_OVERRIDES)
    for c, t in zip(clist, tmp):
        c["key"] = t["key"]
    key_of = {cid: c["key"] for cid, c in cands.items()}
    if has_writein:
        clist.append({"key": C.WRITEIN_KEY, "name": "Write-ins", "party": "OTH", "order": 10**6})

    keys = [c["key"] for c in clist]
    statewide = {k: 0 for k in keys}
    hd_votes: dict[str, dict[str, int]] = {f"AK-HD{n:02d}": {k: 0 for k in keys} for n in range(1, 41)}
    hd_pcts: dict[str, set] = defaultdict(set)
    hd_rep: dict[str, set] = defaultdict(set)
    flags_used = False
    for r in rows:
        k = C.WRITEIN_KEY if is_writein(r) else key_of[r["candidate_id"].strip()]
        v = C.to_int(r.get("total_votes"))
        statewide[k] += v
        u = unit_of(r)
        if u:
            hd_votes[u][k] += v
            pid = r.get("Pct_Id", "").strip()
            if _HD_PCT.match(pid):
                hd_pcts[u].add(pid)
                if r.get("Reporting_flag", "").strip() == "1":
                    hd_rep[u].add(pid)
                    flags_used = True
    units = []
    for u, votes in hd_votes.items():
        p = {"reporting": len(hd_rep[u]), "total": len(hd_pcts[u])} if flags_used else None
        units.append({"id": u, "name": f"House District {int(u[-2:])}", "votes": votes, "precincts": p})
    sw_p = (summary or {}).get("precincts")
    if sw_p is None and flags_used:
        sw_p = {"reporting": sum(len(s) for s in hd_rep.values()), "total": sum(len(s) for s in hd_pcts.values())}
    for c in clist:
        c.pop("source_name", None)
    ts = (summary or {}).get("timestamp") or source_updated_at
    return C.build_result(state=STATE, unit_type="house_district", source=SOURCE, source_url=source_url,
                          source_updated_at=ts, candidates=clist, units=units, statewide_votes=statewide,
                          statewide_precincts=sw_p)


def discover(html: str, page_url: str, section_re: str) -> dict[str, str]:
    """CSV / PDF links whose nearest preceding <h2> matches ``section_re`` (empty dict if none are posted yet)."""
    import lxml.html
    doc = lxml.html.fromstring(html)
    found: dict[str, str] = {}
    for a in doc.xpath("//a[@href]"):
        href = urljoin(page_url, a.get("href"))
        low = href.lower()
        kind = ("csv" if low.endswith(".csv") and "precinct" in low else
                "pdf" if re.search(r"summary[^/]*\.pdf$", low) and "recount" not in low else None)
        if not kind or kind in found:
            continue
        h2 = a.xpath("preceding::h2[1]")
        if h2 and re.search(section_re, h2[0].text_content(), re.I):
            found[kind] = href
    return found


def fetch(session: requests.Session, *, csv_url: str | None = None, pdf_url: str | None = None,
          require_title: str | None = None) -> dict:
    csv_url = csv_url or CONFIG["csv_url"]
    pdf_url = pdf_url or CONFIG["pdf_url"]
    if not csv_url:
        try:
            page = C.get(session, CONFIG["results_page"], extra_ca=EXTRA_CA)
            links = discover(page.text, CONFIG["results_page"], CONFIG["section"])
        except C.FeedError:
            links = {}
        csv_url = links.get("csv") or CONFIG["default_csv"]
        pdf_url = pdf_url or links.get("pdf") or CONFIG["default_pdf"]
    summary = None
    if pdf_url:
        try:
            pdf = C.get(session, pdf_url, extra_ca=EXTRA_CA)
        except C.NotPublished:
            pdf = None
        if pdf is not None:
            try:
                summary = parse_summary_text(pdf_text(pdf.content))
            except Exception as e:          # a damaged/odd PDF only costs us the precinct count
                C.log.warning("AK: summary PDF %s unreadable: %s", pdf_url, e)
    want = require_title if require_title is not None else CONFIG["title"]
    if want and summary and summary.get("title") and not re.search(want, summary["title"], re.I):
        raise C.NotPublished(f"AK: {pdf_url} is {summary['title']!r}, not {want!r} (general file not posted yet)")
    f = C.get(session, csv_url, extra_ca=EXTRA_CA)
    if want and not summary and (f.last_modified or "") < "2026-11-03":
        raise C.NotPublished(f"AK: {csv_url} last modified {f.last_modified}; no summary PDF to confirm the election")
    return parse_csv(f.text, summary=summary, source_url=csv_url, source_updated_at=f.last_modified)

"""Kansas: Secretary of State "Unofficial Kansas Election Results" (ent.sos.ks.gov, static HTML).

Kansas publishes election-night results only as generated static HTML (no JSON/XML/CSV feed; precinct-level files are
posted as .xlsx after the canvass). Every race block on the all-races page (kssos_ent.html) and the federal page
(national.html) carries the statewide totals, "Precincts Reporting: X of Y", and an image map whose <area title=...>
tooltips hold each county's results ("Allen County / 22 of 22 precincts reporting / R-Roger Marshall 1,191").
One page therefore gives statewide + all 105 counties. Candidate names carry a party prefix ("R-", "D-", "L-", "i-")
in general elections; in primaries the party comes from the race title, e.g. "United States Senate (R)".

Access: ent.sos.ks.gov sits behind Cloudflare. As of 2026-11-02 it answers non-browser clients with an "I'm Under
Attack" JS challenge (HTTP 403), which this adapter detects and reports as SourceBlocked (never bypassed).
sos.ks.gov/robots.txt also disallows /ent/ and /api/ on the main host; ent.sos.ks.gov itself has no robots.txt.

Config (env): KS_URLS (comma list, default national.html then kssos_ent.html), KS_RACE (race-title regex, default
exactly "United States Senate"), KS_MIN_DATE (reject pages last updated before this date, default 2026-11-03).
"""

from __future__ import annotations

import re

import lxml.html
import requests

from . import common as C

STATE = "KS"
SOURCE = "Kansas Secretary of State"
BASE = "https://ent.sos.ks.gov/"
CONFIG = {
    "urls": (C.env("KS_URLS") or f"{BASE}national.html,{BASE}kssos_ent.html").split(","),
    "race": C.env("KS_RACE", r"^United States Senate$"),
    "min_date": C.env("KS_MIN_DATE", "2026-11-03"),
}
PREFIX = {"R": "REP", "D": "DEM", "L": "LIB", "LIB": "LIB", "I": "IND", "IND": "IND", "G": "GRN", "REP": "REP",
          "DEM": "DEM", "C": "OTH", "RF": "OTH", "W": "OTH"}
_PREFIX_RE = re.compile(r"^(R|D|L|LIB|I|IND|G|REP|DEM|C|RF|W)-(?=\S)", re.I)
_TITLE_PARTY = re.compile(r"\((R|D|L|LIB|I)\)\s*$")


def _split(label: str) -> tuple[str, str | None]:
    """'R-Roger Marshall' -> ('Roger Marshall', 'REP'); unprefixed names give (name, None)."""
    label = re.sub(r"\s+", " ", label).strip()
    m = _PREFIX_RE.match(label)
    if not m:
        return label, None
    return label[m.end():].strip(), PREFIX[m.group(1).upper()]


def _county_tooltip(title_html: str) -> tuple[str, dict | None, list[tuple[str, int]]]:
    frag = lxml.html.fragment_fromstring(title_html, create_parent="div")
    county = frag.xpath("string(.//span[@class='county'])").strip()
    text = re.sub(r"\s+", " ", frag.text_content())
    m = re.search(r"([\d,]+)\s+of\s+([\d,]+)\s+precincts", text)
    pcts = C.precincts(m.group(1), m.group(2)) if m else None
    rows = []
    for tr in frag.xpath(".//tr"):
        tds = [re.sub(r"\s+", " ", td.text_content()).strip() for td in tr.xpath("./td")]
        if len(tds) == 2 and re.fullmatch(r"[\d,]+", tds[1]):
            rows.append((tds[0], C.to_int(tds[1])))
    return county, pcts, rows


def find_races(doc) -> list[tuple[str, object]]:
    out = []
    for race in doc.xpath("//div[@class='race']"):
        h3 = race.xpath(".//div[contains(@class,'race-heading')]//h3")
        if h3:
            out.append((re.sub(r"\s+", " ", h3[0].text_content()).strip(), race))
    return out


def parse(html: bytes | str, *, race_re: str | None = None, source_url: str = BASE + "kssos_ent.html",
          min_date: str | None = None) -> dict:
    race_re = race_re or CONFIG["race"]
    min_date = CONFIG["min_date"] if min_date is None else min_date
    doc = lxml.html.fromstring(html)
    stamp = doc.xpath("string(//span[@id='time-stamp'])").strip()
    ts = C.local_to_iso(stamp, ["%m/%d/%Y %I:%M %p"], "America/Chicago")
    races = [(t, r) for t, r in find_races(doc) if re.search(race_re, t, re.I)]
    if len(races) != 1:
        titles = [t for t, _ in find_races(doc) if "senat" in t.lower()]
        raise C.NotPublished(f"KS: {len(races)} races match {race_re!r} on {source_url} (senate-like: {titles})")
    if min_date and ts and ts[:10] < min_date:
        raise C.NotPublished(f"KS: page last updated {stamp} ({ts}), before {min_date}: not the 2026 general yet")
    title, race = races[0]
    title_party = _TITLE_PARTY.search(title)
    default_party = PREFIX.get(title_party.group(1).upper()) if title_party else None

    sub = race.xpath("string(.//div[contains(@class,'race-subheading')])")
    m = re.search(r"Precincts Reporting:\s*([\d,]+)\s+of\s+([\d,]+)", sub)
    sw_pcts = C.precincts(m.group(1), m.group(2)) if m else None

    cands: list[dict] = []
    by_name: dict[str, dict] = {}
    statewide: dict[str, int] = {}
    writein = False
    for i, row in enumerate(race.xpath(".//div[@class='race-candidate-list']/div[@class='row']")):
        ps = [re.sub(r"\s+", " ", p.text_content()).strip() for p in row.xpath("./div/p")]
        if len(ps) < 2 or not ps[0] or ps[0].lower() == "total votes":
            continue
        name, party = _split(ps[0])
        if re.search(r"write[\s-]*in", name, re.I):
            writein = True
            statewide[C.WRITEIN_KEY] = statewide.get(C.WRITEIN_KEY, 0) + C.to_int(ps[1])
            continue
        c = {"name": name, "party": party or default_party or "OTH", "order": i}
        cands.append(c)
        by_name[name.lower()] = c
        statewide[name.lower()] = C.to_int(ps[1])
    if not cands:
        raise C.ParseError(f"KS: race {title!r} has no candidate rows")
    C.assign_keys(cands)
    sw_votes = {by_name[n]["key"] if n in by_name else n: v for n, v in statewide.items()}
    if writein:
        cands.append({"key": C.WRITEIN_KEY, "name": "Write-ins", "party": "OTH", "order": 10**6})

    units = []
    for area in race.xpath(".//div[contains(@class,'race-details')]//area[@title]"):
        county, pcts, rows = _county_tooltip(area.get("title"))
        if not county:
            continue
        fips = C.county_fips("KS", county)
        votes = {c["key"]: 0 for c in cands}
        for label, v in rows:
            name, _ = _split(label)
            if re.search(r"write[\s-]*in", name, re.I):
                votes[C.WRITEIN_KEY] = votes.get(C.WRITEIN_KEY, 0) + v
                continue
            c = by_name.get(name.lower())
            if c is None:
                raise C.ParseError(f"KS: {county} lists {label!r}, not a statewide candidate")
            votes[c["key"]] += v
        units.append({"id": fips, "name": C.county_name(fips, "KS"), "votes": votes, "precincts": pcts})
    if len({u["id"] for u in units}) != 105:
        raise C.ParseError(f"KS: {len(units)} county tooltips for {title!r}, expected 105")
    return C.build_result(state=STATE, unit_type="county", source=SOURCE, source_url=source_url,
                          source_updated_at=ts, candidates=cands, units=units, statewide_votes=sw_votes,
                          statewide_precincts=sw_pcts)


def fetch(session: requests.Session, *, urls: list[str] | None = None, race_re: str | None = None) -> dict:
    last: Exception | None = None
    for url in urls or CONFIG["urls"]:
        try:
            page = C.get(session, url.strip())
        except C.SourceBlocked:
            raise                               # same host: do not keep knocking on a challenge page
        except C.NotPublished as e:
            last = e
            continue
        try:
            return parse(page.content, race_re=race_re, source_url=url.strip())
        except C.NotPublished as e:
            last = e
    raise last or C.NotPublished("KS: no page configured")

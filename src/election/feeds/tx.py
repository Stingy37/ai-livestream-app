"""Texas: Secretary of State Election Night Returns (Civix "IVIS" ENR, goelect.txelections.civixapps.com).

Since 2025 the SOS results site is the Civix ENR at https://goelect.txelections.civixapps.com/ivis-enr-ui/ (the old
results.texas-election.com portal is frozen at 2024 and sits behind a Cloudflare challenge). The app reads
base64-wrapped JSON from a public, unauthenticated API:

    /api-ivis-system/api/s3/enr/electionConstants           -> every election, by year and type (GE = general)
    /api-ivis-system/api/s3/enr/election/<id>               -> statewide: Home (timestamp, reporting), Federal races
    /api-ivis-system/api/s3/enr/election/countyInfo/<id>    -> every county (1..254, alphabetical) x every race

Each response is ``{"<Section>": "<base64 of JSON>"}``. Counties are keyed 1..254 in the SOS's own alphabetical order
(which differs from FIPS order around the "Mc" names), so FIPS comes from the county name. Declared write-in candidates are listed individually with party "W"; they are
summed into one ``writein`` line. ``precincts`` uses the race-level precinct counts (PR/TP) summed over counties.

Config (env): TX_ELECTION_ID (skip discovery), TX_ELECTION_YEAR (2026), TX_ELECTION_NAME (regex for the
electionConstants entry, default "NOVEMBER GENERAL"), TX_RACE (regex on the race name, default U.S. Senator).
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import requests

from . import common as C

STATE = "TX"
SOURCE = "Texas Secretary of State"
HOST = "https://goelect.txelections.civixapps.com"
API = HOST + "/api-ivis-system/api/s3/enr"
PAGE = HOST + "/ivis-enr-ui/races"
CONFIG = {
    "election_id": C.env("TX_ELECTION_ID"),               # 53815 = 2026 NOVEMBER GENERAL ELECTION (discovered)
    "year": C.env("TX_ELECTION_YEAR", "2026"),
    "election_type": C.env("TX_ELECTION_TYPE", "GE"),
    "election_name": C.env("TX_ELECTION_NAME", r"NOVEMBER GENERAL"),
    "race": C.env("TX_RACE", r"^U\.?\s*S\.?\s*SENATOR\b"),
}
PARTY = {"REP": "REP", "DEM": "DEM", "LIB": "LIB", "L": "LIB", "GRN": "GRN", "G": "GRN", "IND": "IND", "I": "IND"}


def unwrap(payload: dict, section: str) -> Any:
    """Decode one base64-JSON section of a Civix ENR response."""
    raw = payload.get(section)
    if raw is None:
        raise C.ParseError(f"TX: section {section!r} missing (have {sorted(payload)[:12]})")
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(base64.b64decode(raw))
    except (ValueError, TypeError) as e:
        raise C.ParseError(f"TX: section {section!r} is not base64 JSON ({e})") from e


def discover_election_id(constants: dict, year: str, etype: str, name_re: str) -> tuple[int, str]:
    info = unwrap(constants, "upload")["electionInfo"]
    found = []
    for eid, e in (info.get(str(year), {}).get(etype) or {}).items():
        if re.search(name_re, e.get("N", ""), re.I):
            found.append((int(e.get("ID", eid)), e.get("N", "")))
    if len(found) != 1:
        raise C.NotPublished(f"TX: {len(found)} elections match {year}/{etype}/{name_re!r}: {found}")
    return found[0]


def _find_race(races: list[dict], race_re: str) -> dict:
    hits = [r for r in races if re.search(race_re, r.get("N", ""), re.I)]
    if len(hits) != 1:
        raise C.ParseError(f"TX: {len(hits)} races match {race_re!r}: {[r.get('N') for r in hits]}")
    return hits[0]


def _cand(raw: dict, order: int) -> dict:
    p = (raw.get("P") or "").upper()
    return {"source_id": str(raw.get("ID", raw.get("id"))), "name": C.display_name(raw.get("N", "")),
            "last": (raw.get("LN") or "").strip(), "party": PARTY.get(p, "OTH"), "write_in": p == "W",
            "order": raw.get("O", order) * 100 + order}


def parse(election: dict, county_info: dict, *, race_re: str | None = None, election_id: Any = None) -> dict:
    """Build the Live results dict from the two decoded-on-the-fly API responses (pure, no network)."""
    race_re = race_re or CONFIG["race"]
    home = unwrap(election, "Home")
    federal = unwrap(election, "Federal")
    race = _find_race(federal.get("Races", []), race_re)
    rid = str(race["id"])

    cands, writein_ids = [], set()
    for i, raw in enumerate(race.get("Candidates", [])):
        c = _cand(raw, i)
        if c["write_in"]:
            writein_ids.add(c["source_id"])
        else:
            cands.append(c)
    C.assign_keys(cands)
    key_of = {c["source_id"]: c["key"] for c in cands}
    if writein_ids:
        cands.append({"key": C.WRITEIN_KEY, "name": "Write-ins", "party": "OTH", "order": 10**6})
        key_of.update({w: C.WRITEIN_KEY for w in writein_ids})

    statewide = {c["key"]: 0 for c in cands}
    for raw in race.get("Candidates", []):
        statewide[key_of[str(raw.get("ID"))]] += C.to_int(raw.get("V"))

    counties = unwrap(county_info, "upload")
    units = []
    for n_str, cty in counties.items():
        fips = C.county_fips("TX", cty.get("N", ""))   # the 1..254 index is SOS alphabetical order, not FIPS order
        r = (cty.get("Races") or {}).get(rid)
        if r is None:
            continue                       # race not on this county's ballot (never for a statewide race)
        votes = {c["key"]: 0 for c in cands}
        for cid, raw in (r.get("C") or {}).items():
            k = key_of.get(str(raw.get("id", cid)))
            if k is None:
                raise C.ParseError(f"TX: county {fips} has candidate {cid} not in the statewide race")
            votes[k] += C.to_int(raw.get("V"))
        units.append({"id": fips, "name": C.county_name(fips, "TX"), "votes": votes,
                      "precincts": C.precincts(r.get("PR"), r.get("TP"))})
    if len(units) != 254 or len({u["id"] for u in units}) != 254:
        raise C.ParseError(f"TX: {len(units)} counties carry the race, expected 254 distinct")

    ts = C.local_to_iso(home.get("LastUpdatedTime", ""), ["%b %d, %Y %H:%M:%S"], "America/Chicago")
    for c in cands:
        c.pop("source_id", None), c.pop("last", None), c.pop("write_in", None)
    m = re.search(r"enr/(\d+)/", str(election.get("Version", "")))
    eid = election_id or (m.group(1) if m else "?")
    return C.build_result(state=STATE, unit_type="county", source=SOURCE,
                          source_url=f"{API}/election/countyInfo/{eid}", source_updated_at=ts,
                          candidates=cands, units=units, statewide_votes=statewide)


def fetch(session: requests.Session, *, election_id: Any = None, race_re: str | None = None) -> dict:
    eid = election_id or CONFIG["election_id"]
    if not eid:
        consts = C.get(session, f"{API}/electionConstants", conditional=False).json()
        eid, _ = discover_election_id(consts, CONFIG["year"], CONFIG["election_type"], CONFIG["election_name"])
    election = C.get(session, f"{API}/election/{eid}", conditional=False).json()
    county = C.get(session, f"{API}/election/countyInfo/{eid}", conditional=False).json()
    return parse(election, county, race_re=race_re, election_id=eid)

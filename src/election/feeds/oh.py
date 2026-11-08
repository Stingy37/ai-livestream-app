"""Ohio: Secretary of State "Ohio Decides" election-night reporting, NIST 1500-100 XML feed.

https://liveresults.ohiosos.gov/Api/v1/download?filename=VSSC1622XmlFileBlob serves the current election as an
ElectionReport in Ohio's implementation of the draft NIST SP 1500-100 / IEEE 1622 results format (documented at
https://liveresults.ohiosos.gov/Content/PDF/P1622Documentation.pdf). One file has every contest with a statewide
VoteCounts plus one per county (GpUnitId), and each county GpUnit carries SubUnitsReported / TotalSubUnits (precincts).
The feed sends ETag + Last-Modified and Cache-Control max-age=15, so conditional GETs are cheap.

The pre-election file is already the 2026 general (Election Date 2026-11-03, Type General) with IsTest="true" and all
counts 0. ``fetch`` refuses a file flagged IsTest unless ``allow_test=True`` so test numbers can never reach the
stream. Write-in candidates are listed but "Unofficial results for write-in (WI) candidates will not be reported" on
election night; they are summed into ``writein`` and only shown when non-zero.

Config (env): OH_FEED_URL, OH_RACE (contest-name regex, default "U.S. Senator"), OH_ELECTION_DATE (2026-11-03).
"""

from __future__ import annotations

import datetime as dt
import re

import requests
from lxml import etree

from . import common as C

STATE = "OH"
SOURCE = "Ohio Secretary of State"
CONFIG = {
    "url": C.env("OH_FEED_URL", "https://liveresults.ohiosos.gov/Api/v1/download?filename=VSSC1622XmlFileBlob"),
    "race": C.env("OH_RACE", r"^U\.?\s*S\.?\s*Senator\b"),
    "election_date": C.env("OH_ELECTION_DATE", "2026-11-03"),
}
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
PARTY_ABBR = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "GRE": "GRN", "GRN": "GRN", "INDEP": "IND", "NONPRTYCAN": "IND"}


def _ls(el) -> str:
    """Text of the first LanguageString under ``el``."""
    if el is None:
        return ""
    s = el.find(".//{*}LanguageString")
    return (s.text or "").strip() if s is not None else (el.text or "").strip()


def parse(xml: bytes, *, race_re: str | None = None, allow_test: bool = False, election_date: str | None = None,
          source_url: str | None = None) -> dict:
    race_re = race_re or CONFIG["race"]
    election_date = CONFIG["election_date"] if election_date is None else election_date
    try:
        root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
    except etree.XMLSyntaxError as e:
        raise C.ParseError(f"OH: not XML ({e})") from e
    if root.get("IsTest", "false").strip().lower() in ("true", "1") and not allow_test:   # xsd:boolean: true/1
        raise C.TestData("OH: feed is flagged IsTest=\"true\" (pre-election test file)")
    election = root.find("{*}Election")
    if election is None:
        raise C.ParseError("OH: no Election element")
    if election_date and election.get("Date") != election_date:
        raise C.NotPublished(f"OH: feed is the {election.get('Date')} {election.get('Type')} election, "
                             f"not {election_date}")

    gp = {g.get("ObjectId"): g for g in root.iter("{*}GpUnit")}
    parties = {p.get("ObjectId"): p for p in root.iter("{*}Party")}
    persons = {p.get("ObjectId"): p for p in root.iter("{*}Person")}
    cands_x = {c.get("ObjectId"): c for c in root.iter("{*}Candidate")}
    contests = [c for c in election.iter("{*}Contest") if re.search(race_re, c.get("Name", ""), re.I)]
    if len(contests) != 1:
        raise C.ParseError(f"OH: {len(contests)} contests match {race_re!r}: {[c.get('Name') for c in contests]}")
    contest = contests[0]

    cands, sel_key, writein = [], {}, False
    sels = contest.findall("{*}BallotSelection")
    for i, bs in enumerate(sels):
        cid = (bs.findtext("{*}CandidateId") or "").strip()
        cx = cands_x.get(cid)
        if bs.get("IsWriteIn", "false").lower() == "true":
            sel_key[bs.get("ObjectId")] = C.WRITEIN_KEY
            writein = True
            continue
        if cx is None:
            raise C.ParseError(f"OH: selection {bs.get('ObjectId')} has unknown candidate {cid!r}")
        party = parties.get((cx.findtext("{*}PartyId") or "").strip())
        abbr = (party.get("Abbreviation") if party is not None else "") or ""
        pname = _ls(party.find("{*}Name")) if party is not None else ""
        person = persons.get((cx.findtext("{*}PersonId") or "").strip())
        last = (person.findtext("{*}LastName") or "").strip() if person is not None else ""
        c = {"sel": bs.get("ObjectId"), "name": _ls(cx.find("{*}BallotName")), "last": last, "order": i,
             "party": PARTY_ABBR.get(abbr.upper()) or C.norm_party(pname)}
        cands.append(c)
    C.assign_keys(cands)
    for c in cands:
        sel_key[c.pop("sel")] = c["key"]
        c.pop("last", None)
    if writein:
        cands.append({"key": C.WRITEIN_KEY, "name": "Write-ins", "party": "OTH", "order": 10**6})
    keys = [c["key"] for c in cands]

    statewide = {k: 0 for k in keys}
    by_unit: dict[str, dict[str, int]] = {}
    for bs in sels:
        k = sel_key[bs.get("ObjectId")]
        for vc in bs.iter("{*}VoteCounts"):
            if vc.get("Type", "Total") != "Total":
                continue
            g = gp.get((vc.findtext("{*}GpUnitId") or "").strip())
            if g is None:
                raise C.ParseError("OH: VoteCounts for an unknown GpUnit")
            n = C.to_int(vc.get("Count"))
            if g.get("Type") == "State":
                statewide[k] += n
            elif g.get("Type") == "County":
                by_unit.setdefault(g.get("ObjectId"), {kk: 0 for kk in keys})[k] += n
    if writein and statewide[C.WRITEIN_KEY] == 0 and all(v[C.WRITEIN_KEY] == 0 for v in by_unit.values()):
        cands = [c for c in cands if c["key"] != C.WRITEIN_KEY]          # not reported on election night
        keys.remove(C.WRITEIN_KEY)
        statewide.pop(C.WRITEIN_KEY)
        for v in by_unit.values():
            v.pop(C.WRITEIN_KEY)

    units = []
    for oid, votes in by_unit.items():
        g = gp[oid]
        fips = C.county_fips("OH", g.get("Name", ""))
        units.append({"id": fips, "name": C.county_name(fips, "OH"), "votes": votes,
                      "precincts": C.precincts(g.get("SubUnitsReported"), g.get("TotalSubUnits"))})
    if len({u["id"] for u in units}) != 88:
        raise C.ParseError(f"OH: {len(units)} counties for {contest.get('Name')!r}, expected 88")
    gen = root.get("GeneratedDate")
    ts = C.iso(dt.datetime.fromisoformat(gen.replace("Z", "+00:00"))) if gen else None
    return C.build_result(state=STATE, unit_type="county", source=SOURCE, source_url=source_url or CONFIG["url"],
                          source_updated_at=ts, candidates=cands, units=units, statewide_votes=statewide)


def fetch(session: requests.Session, *, allow_test: bool = False, url: str | None = None) -> dict:
    url = url or CONFIG["url"]
    f = C.get(session, url)
    return parse(f.content, allow_test=allow_test, source_url=url)

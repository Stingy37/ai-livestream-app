"""Michigan: Secretary of State / Bureau of Elections results on MVIC (mvic.sos.state.mi.us).

What is known (from the official michigan.gov "Election results and data" page and the MVIC page code):

* michigan.gov links the 2026 general's "Election results" to
  https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-3-2026 (type C = county results).
* That page lists elections in <select id="ElectionDateId"> (e.g. 699 = "11/5/2024 STATE GENERAL") and loads
  county results with jQuery from /VoteHistory/GetCountyVoteRecords?electionId=<id> (an HTML fragment); precinct
  results come from /VoteHistory/GetPrecinctInfo?electionId=<id>&countyCode=<1..83>, and a bulk download from
  /VoteHistory/GetElectionResultFile?electionId=<id>.
* The older election-night site used the pattern https://mielections.us/election/results/<YYYY><CODE>_CENR.html
  (michigan.gov still links 2016SG1_CENR.html); a 2026 page would be 2026GEN_CENR.html.

What blocks a working parser here: as of 2026-11-02 MVIC answers this client with a Cloudflare managed challenge
(HTTP 403, every path including robots.txt) and mielections.us does not accept TCP connections from this network, so
neither the 2026 nor any past results fragment could be observed. ``fetch`` therefore discovers the election id,
tries the official endpoints, raises SourceBlocked when challenged, and, if a body does come back (another network,
or the challenge lifted), saves it under output/election/raw/MI/ and raises ParseError so a parser can be written
against the real format in minutes. It never returns guessed numbers.

Config (env): MI_ELECTION_ID (skip discovery), MI_ELECTION_LABEL (option text prefix, default "11/3/2026").
"""

from __future__ import annotations

import re
from pathlib import Path

import requests

from . import common as C

STATE = "MI"
SOURCE = "Michigan Secretary of State"
MVIC = "https://mvic.sos.state.mi.us"
CONFIG = {
    "index_url": C.env("MI_INDEX_URL", MVIC + "/votehistory/Index?type=C&electionDate=11-3-2026"),
    "county_url": MVIC + "/VoteHistory/GetCountyVoteRecords?electionId={id}",
    "file_url": MVIC + "/VoteHistory/GetElectionResultFile?electionId={id}",
    "enr_url": C.env("MI_ENR_URL", "https://mielections.us/election/results/2026GEN_CENR.html"),
    "election_id": C.env("MI_ELECTION_ID"),
    "label": C.env("MI_ELECTION_LABEL", "11/3/2026"),
    "raw_dir": Path(C.env("MI_RAW_DIR", str(C.REPO / "output" / "election" / "raw" / "MI"))),
}


def discover_election_id(index_html: str, label: str | None = None) -> int:
    """Election id from the MVIC results page's <select id="ElectionDateId"> (option text starts with ``label``)."""
    import lxml.html
    label = label or CONFIG["label"]
    doc = lxml.html.fromstring(index_html)
    opts = [(o.get("value"), re.sub(r"\s+", " ", o.text_content()).strip())
            for o in doc.xpath("//select[@id='ElectionDateId']//option")]
    hits = [int(v) for v, t in opts if v and v != "0" and t.startswith(label)]
    if len(hits) != 1:
        raise C.NotPublished(f"MI: {len(hits)} MVIC elections labelled {label!r} (options: {opts[:6]})")
    return hits[0]


def parse_county_records(fragment: bytes) -> dict:
    """Not implemented: the GetCountyVoteRecords fragment has not been observable from this network (see module doc)."""
    raise C.ParseError("MI: county-results parser not written yet: no sample of the MVIC fragment could be fetched")


def fetch(session: requests.Session, *, election_id: int | None = None) -> dict:
    eid = election_id or CONFIG["election_id"]
    if not eid:
        page = C.get(session, CONFIG["index_url"], conditional=False)
        eid = discover_election_id(page.text)
    url = CONFIG["county_url"].format(id=eid)
    f = C.get(session, url, conditional=False)
    CONFIG["raw_dir"].mkdir(parents=True, exist_ok=True)
    sample = CONFIG["raw_dir"] / f"GetCountyVoteRecords_{eid}_{C.utcnow().replace(':', '')}.html"
    C.write_atomic_bytes(sample, f.content)
    try:
        return parse_county_records(f.content)
    except C.ParseError as e:
        raise C.ParseError(f"{e}; sample saved to {sample}") from None

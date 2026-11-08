"""Offline tests for the election-night results adapters (src/election/feeds).

Fixtures are trimmed copies of the states' own official files (data only, never executed):

* TX  tx_58315_*  2026 Republican primary runoff (U.S. Senate, Cornyn v Paxton), Civix ENR API, final unofficial
      tx_53815_*  2026 November general: the zero file already published on the same API (structure, write-ins)
      tx_electionconstants.json  the election list used for discovery
* AK  ak_2026prim_*  2026 top-four primary, U.S. Senator rows of GA_ENR_Precinct_State_of_Alaska.csv + summary PDF text
* KS  ks_*  ent.sos.ks.gov pages (2026 primary U.S. Senate (R); 2024 general President), via the Internet Archive
* ME  me_2024gen_us_senator.xlsx  Maine SOS "US Senator FINAL.xlsx" (2024 general, by town), via the Internet Archive
* OH  oh_2026gen_test_vssc1622.xml.gz  the live 2026 general pre-election test file (IsTest, zeros), U.S. Senator only
* MI  mi_mvic_index_election_select.html  the election selector of the MVIC results page (2025 copy)
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from lxml import etree

from election import feeds
from election.feeds import ak, common as C, ks, me, mi, oh, tx

FX = Path(__file__).parent / "fixtures"


def raw(name: str) -> bytes:
    data = (FX / name).read_bytes()
    return gzip.decompress(data) if name.endswith(".gz") else data


def js(name: str):
    return json.loads(raw(name))


def assert_schema(r: dict, state: str, n_units: int):
    C.validate(r)
    assert r["state"] == state and r["race"] == "senate"
    assert len(r["units"]) == n_units
    assert r["fetched_at"].endswith("Z")
    assert r["total_votes"] == sum(c["votes"] for c in r["candidates"])
    votes = [c["votes"] for c in r["candidates"]]
    assert votes == sorted(votes, reverse=True)


# ---------------------------------------------------------------- fake HTTP

class FakeResp:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}


class FakeSession:
    """Routes URLs (by substring) to canned responses and records every request."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers=None, timeout=None, verify=True):
        self.calls.append((url, dict(headers or {})))
        for key, resp in self.routes.items():
            if key in url:
                return resp(url, headers or {}) if callable(resp) else resp
        return FakeResp(404, b"not found")


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CACHE_DIR", tmp_path / "http")
    monkeypatch.setattr(C, "MIN_HOST_INTERVAL_S", 0.0)
    monkeypatch.setattr(C, "RAW_DIR", None)
    monkeypatch.setattr(C.time, "sleep", lambda s: None)


CF_CHALLENGE = FakeResp(403, b"<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
                             b"<script>window._cf_chl_opt={}</script></body></html>", {"Server": "cloudflare"})


# ---------------------------------------------------------------- common

def test_party_normalisation():
    cases = {"REP": "REP", "Republican": "REP", "R": "REP", "DEM": "DEM", "Democratic": "DEM", "LIB": "LIB",
             "Libertarian": "LIB", "GRN": "GRN", "Green Independent": "GRN", "Independent": "IND", "NON": "IND",
             "UND": "IND", "Nonparty candidate": "IND", "": "OTH", None: "OTH", "AIP": "OTH", "W": "OTH"}
    for raw_p, want in cases.items():
        assert C.norm_party(raw_p) == want, raw_p


def test_candidate_keys_and_names():
    cs = [{"name": "Sullivan, Dan S.", "order": 1}, {"name": "Sullivan, Daniel J. Jr.", "order": 2},
          {"name": "JOHN CORNYN (I)", "order": 3}, {"name": "Carol \"Kitty\" Hafner", "order": 4},
          {"name": "John Smith", "order": 5}, {"name": "Jane Smith", "order": 6}, {"name": "José Núñez", "order": 7}]
    C.assign_keys(cs)
    assert [c["key"] for c in cs] == ["sullivan", "sullivan_jr", "cornyn", "hafner", "smith", "smith_jane", "nunez"]
    assert C.display_name("SULLIVAN, DAN S.") == "Dan S. Sullivan"
    assert C.display_name("JOHN CORNYN (I)") == "John Cornyn"
    assert C.display_name('BRADFORD "BRAD" HALL') == 'Bradford "Brad" Hall'
    assert C.display_name("Sullivan, Daniel J. Jr.") == "Daniel J. Sullivan Jr."
    assert C.display_name("KEVIN MCCARTHY") == "Kevin McCarthy"


def test_county_fips():
    assert C.county_fips("TX", "DE WITT") == "48123"
    assert C.county_fips("TX", "MCCULLOCH") == "48307"
    assert C.county_fips("MI", "ST. CLAIR") == "26147"
    assert C.county_fips("KS", "Johnson County") == "20091"
    assert C.county_fips("OH", "Franklin") == "39049"
    with pytest.raises(C.ParseError):
        C.county_fips("OH", "Atlantis")


def test_http_conditional_get_and_blocks(tmp_path):
    hits = {"n": 0}

    def file(url, headers):
        hits["n"] += 1
        if headers.get("If-None-Match") == '"v1"':
            return FakeResp(304, b"", {"ETag": '"v1"'})
        return FakeResp(200, b"payload", {"ETag": '"v1"', "Last-Modified": "Tue, 03 Nov 2026 02:00:00 GMT"})

    s = FakeSession({"/file": file, "/cf": CF_CHALLENGE, "/flaky": FakeResp(503, b"busy")})
    a = C.get(s, "https://x.gov/file")
    b = C.get(s, "https://x.gov/file")
    assert a.content == b.content == b"payload" and not a.not_modified and b.not_modified
    assert a.last_modified == "2026-11-03T02:00:00Z"
    assert s.calls[1][1]["If-None-Match"] == '"v1"'
    assert "User-Agent" not in s.calls[0][1]           # the UA lives on the session, see make_session
    assert C.make_session().headers["User-Agent"] == C.USER_AGENT
    assert "@" not in C.USER_AGENT
    with pytest.raises(C.SourceBlocked):
        C.get(s, "https://x.gov/cf")
    assert sum(1 for u, _ in s.calls if u.endswith("/cf")) == 1    # a challenge is never retried
    with pytest.raises(C.NotPublished):
        C.get(s, "https://x.gov/missing")
    with pytest.raises(C.FeedError):
        C.get(s, "https://x.gov/flaky", retries=1)
    assert sum(1 for u, _ in s.calls if u.endswith("/flaky")) == 2


def test_write_json_atomic(tmp_path):
    p = tmp_path / "live" / "TX.json"
    C.write_json_atomic(p, {"a": 1})
    C.write_json_atomic(p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 2}
    assert [x.name for x in p.parent.iterdir()] == ["TX.json"]


# ---------------------------------------------------------------- TX

def test_tx_runoff_2026():
    r = tx.parse(js("tx_58315_election.json"), js("tx_58315_countyinfo.json.gz"))
    assert_schema(r, "TX", 254)
    assert [(c["key"], c["name"], c["party"], c["votes"]) for c in r["candidates"]] == [
        ("paxton", "Ken Paxton", "REP", 888196), ("cornyn", "John Cornyn", "REP", 503438)]
    assert r["total_votes"] == 1391634
    assert r["precincts"] == {"reporting": 9534, "total": 9534}
    assert r["source_updated_at"] == "2026-06-13T00:23:34Z"            # "Jun 12, 2026 19:23:34" Central
    harris = next(u for u in r["units"] if u["id"] == "48201")
    assert harris["votes"] == {"cornyn": 52041, "paxton": 93872} and harris["precincts"]["total"] == 1225
    assert next(u for u in r["units"] if u["id"] == "48307")["name"] == "McCulloch"
    assert sum(u["total"] for u in r["units"]) == r["total_votes"]
    assert r["source_url"].endswith("/countyInfo/58315")


def test_tx_general_zero_file():
    r = tx.parse(js("tx_53815_election.json"), js("tx_53815_countyinfo.json.gz"))
    assert_schema(r, "TX", 254)
    assert {c["key"]: c["party"] for c in r["candidates"]} == {
        "paxton": "REP", "talarico": "DEM", "brown": "LIB", "writein": "OTH"}
    assert r["total_votes"] == 0 and r["precincts"]["reporting"] == 0 and r["precincts"]["total"] > 9000


def test_tx_discovery_and_fetch_offline():
    eid, name = tx.discover_election_id(js("tx_electionconstants.json"), "2026", "GE", tx.CONFIG["election_name"])
    assert (eid, name) == (53815, "2026 NOVEMBER GENERAL ELECTION")
    with pytest.raises(C.NotPublished):
        tx.discover_election_id(js("tx_electionconstants.json"), "2026", "GE", "DECEMBER")
    s = FakeSession({"/electionConstants": FakeResp(200, raw("tx_electionconstants.json")),
                     "/election/countyInfo/53815": FakeResp(200, raw("tx_53815_countyinfo.json.gz")),
                     "/election/53815": FakeResp(200, raw("tx_53815_election.json"))})
    r = tx.fetch(s)
    assert r["source_url"] == f"{tx.API}/election/countyInfo/53815"
    assert len(s.calls) == 3


# ---------------------------------------------------------------- AK

def test_ak_summary_text():
    s = ak.parse_summary_text(raw("ak_2026prim_summary_p1.txt").decode())
    assert s == {"title": "2026 PRIMARY ELECTION", "status": "OFFICIAL RESULTS",
                 "timestamp": "2026-08-31T20:43:34Z", "precincts": {"reporting": 401, "total": 403}}


def test_ak_precinct_csv_primary_2026():
    summary = ak.parse_summary_text(raw("ak_2026prim_summary_p1.txt").decode())
    r = ak.parse_csv(raw("ak_2026prim_precinct_senate.csv.gz").decode(), summary=summary, source_url="u")
    assert_schema(r, "AK", 40)
    assert r["unit_type"] == "house_district"   # same as data/election/baseline/AK.json
    top = [(c["key"], c["party"], c["votes"]) for c in r["candidates"][:4]]
    assert top == [("peltola", "DEM", 82244), ("sullivan", "REP", 68726), ("sullivan_jr", "OTH", 4107),
                   ("leslie", "DEM", 1850)]
    assert r["total_votes"] == 166004                       # = "Total Votes 166,004" on the official summary
    assert r["precincts"] == {"reporting": 401, "total": 403}
    assert [u["id"] for u in r["units"]] == [f"AK-HD{n:02d}" for n in range(1, 41)]
    assert all(u["precincts"] is None for u in r["units"])  # Reporting_flag is never set in the published files
    overseas = r["total_votes"] - sum(u["total"] for u in r["units"])
    assert 0 < overseas < 2000                                # HD99 federal overseas absentee: statewide only


def test_ak_unit_mapping_and_writein():
    assert ak.unit_of({"Pct_Id": "01-600", "Precinct_name": "01-600 Ketchikan No. 1"}) == "AK-HD01"
    assert ak.unit_of({"Pct_Id": "", "Precinct_name": "District 1 - Early Voting"}) == "AK-HD01"
    assert ak.unit_of({"Pct_Id": "07", "Precinct_name": "District 7  - Question"}) == "AK-HD07"
    assert ak.unit_of({"Pct_Id": "99", "Precinct_name": "HD99 Fed Overseas Absentee"}) is None
    text = raw("ak_2026prim_precinct_senate.csv.gz").decode().splitlines()
    hdr, row = text[0], text[1]
    wi = row.replace('"Darden, Dustin Thomas House",C', '"Write-in 60",W').replace(",47,", ",999,")
    r = ak.parse_csv("\n".join([hdr, row, wi]), source_url="u")
    assert "writein" in {c["key"] for c in r["candidates"]}


def test_ak_discovery_and_primary_guard(monkeypatch):
    html = ('<html><body><h2>2026 General Election &#x2013; November 3, 2026</h2><ul>'
            '<li><a href="https://www.elections.alaska.gov/enr26/results/ElectionSummaryReportRPT.pdf">Summary</a></li>'
            '<li><a href="/enr26/results/GA_ENR_Precinct_State_of_Alaska.csv">Results Per Precinct</a></li></ul>'
            '<h2>Search Official Election Results</h2><a href="/results/24GENR/ENRbyPrecinct.csv">old</a></body></html>')
    links = ak.discover(html, "https://www.elections.alaska.gov/election-results/", r"2026 General Election")
    assert links == {"pdf": "https://www.elections.alaska.gov/enr26/results/ElectionSummaryReportRPT.pdf",
                     "csv": "https://www.elections.alaska.gov/enr26/results/GA_ENR_Precinct_State_of_Alaska.csv"}
    # Today the live /enr26/ files are still the August primary: fetch must refuse them, not publish them.
    monkeypatch.setattr(ak, "pdf_text", lambda content, pages=1: raw("ak_2026prim_summary_p1.txt").decode())
    s = FakeSession({".pdf": FakeResp(200, b"%PDF-1.7"),
                     ".csv": FakeResp(200, raw("ak_2026prim_precinct_senate.csv.gz"),
                                      {"Last-Modified": "Mon, 31 Aug 2026 21:07:47 GMT"})})
    with pytest.raises(C.NotPublished):
        ak.fetch(s, csv_url="https://e/x.csv", pdf_url="https://e/x.pdf")
    r = ak.fetch(s, csv_url="https://e/x.csv", pdf_url="https://e/x.pdf", require_title="")
    assert r["total_votes"] == 166004


# ---------------------------------------------------------------- KS

def test_ks_primary_2026_senate():
    r = ks.parse(raw("ks_2026prim_senate_r.html.gz"), race_re=r"^United States Senate \(R\)$", min_date="")
    assert_schema(r, "KS", 105)
    assert [(c["key"], c["party"], c["votes"]) for c in r["candidates"]] == [
        ("marshall", "REP", 267972), ("naramore", "REP", 67496)]
    assert r["precincts"] == {"reporting": 4150, "total": 4150}
    assert r["source_updated_at"] == "2026-08-07T22:29:00Z"
    jo = next(u for u in r["units"] if u["id"] == "20091")
    assert jo["name"] == "Johnson" and jo["votes"] == {"marshall": 53216, "naramore": 16831}
    assert jo["precincts"] == {"reporting": 587, "total": 587}
    assert sum(u["total"] for u in r["units"]) == r["total_votes"]


def test_ks_general_2024_party_prefixes():
    r = ks.parse(raw("ks_2024gen_president.html.gz"), race_re=r"^President / Vice President$", min_date="")
    assert_schema(r, "KS", 105)
    assert [(c["key"], c["party"]) for c in r["candidates"]] == [
        ("trump", "REP"), ("harris", "DEM"), ("kennedy", "IND"), ("oliver", "LIB")]
    assert r["total_votes"] == 1281725 == sum(u["total"] for u in r["units"])


def test_ks_guards():
    with pytest.raises(C.NotPublished):                    # the default race is the general's "United States Senate"
        ks.parse(raw("ks_2026prim_senate_r.html.gz"))
    with pytest.raises(C.NotPublished):                    # a page last updated before election day is refused
        ks.parse(raw("ks_2024gen_president.html.gz"), race_re=r"^President")
    s = FakeSession({"ent.sos.ks.gov": CF_CHALLENGE})
    with pytest.raises(C.SourceBlocked):
        ks.fetch(s)
    assert len(s.calls) == 1                               # stops at the first challenge on the host


# ---------------------------------------------------------------- ME

def test_me_towns_to_counties_2024():
    r = me.parse_xlsx(raw("me_2024gen_us_senator.xlsx"), source_url="u")
    assert_schema(r, "ME", 16)
    assert [(c["key"], c["party"], c["votes"]) for c in r["candidates"]] == [
        ("king", "IND", 427331), ("kouzounas", "REP", 284338), ("costello", "DEM", 88891), ("cherry", "IND", 20222)]
    assert r["precincts"] is None
    cum = next(u for u in r["units"] if u["id"] == "23005")
    assert cum["name"] == "Cumberland"
    towns = r["towns"]
    assert len(towns) > 450 and {t["county"] for t in towns} == {u["id"] for u in r["units"]}
    auburn = next(t for t in towns if t["id"] == "23001-auburn")
    assert auburn["votes"] == {"cherry": 309, "costello": 1288, "king": 6659, "kouzounas": 4000}
    for u in r["units"]:
        assert u["total"] == sum(t["total"] for t in towns if t["county"] == u["id"])
    assert 0 < r["total_votes"] - sum(u["total"] for u in r["units"]) < 10000   # STATE UOCAVA: statewide only


def test_me_discovery_prefers_general_file():
    html = ('<a href="/sos/files/1-20US-20Senate-20Dem-20--20FINAL.xlsx">Democratic (Excel)</a>'
            '<a href="/sos/files/US-20Senator-201st-20Choice.xlsx">U.S. Senator (Excel)</a>'
            '<a href="/sos/files/Governor.xlsx">Governor (Excel)</a>')
    got = me.discover(html, "https://www.maine.gov/sos/x")
    assert got[0] == "https://www.maine.gov/sos/files/US-20Senator-201st-20Choice.xlsx" and len(got) == 2
    s = FakeSession({"www.maine.gov": FakeResp(403, b"<H1>403 ERROR</H1>Request blocked.", {"Server": "CloudFront"})})
    with pytest.raises(C.SourceBlocked):
        me.fetch(s)


# ---------------------------------------------------------------- OH

def test_oh_test_file_is_refused_by_default():
    with pytest.raises(C.TestData):
        oh.parse(raw("oh_2026gen_test_vssc1622.xml.gz"))
    with pytest.raises(C.NotPublished):
        oh.parse(raw("oh_2026gen_test_vssc1622.xml.gz"), allow_test=True, election_date="2026-11-04")


def test_oh_istest_flag_flip():
    """Election night: the same file with IsTest flipped (or dropped) is accepted; "1" (xsd:boolean) still means test."""
    root = etree.fromstring(raw("oh_2026gen_test_vssc1622.xml.gz"))
    root.set("IsTest", "1")
    with pytest.raises(C.TestData):
        oh.parse(etree.tostring(root))
    for flag in ("false", "0", None):
        if flag is None:
            del root.attrib["IsTest"]
        else:
            root.set("IsTest", flag)
        r = oh.parse(etree.tostring(root))
        assert r["total_votes"] == 0 and len(r["units"]) == 88


def test_loop_backs_off_blocked_sources(tmp_path, monkeypatch):
    calls = {"KS": 0, "TX": 0}
    good = tx.parse(js("tx_58315_election.json"), js("tx_58315_countyinfo.json.gz"))

    def ks(session):
        calls["KS"] += 1
        raise C.SourceBlocked("challenge")

    def txf(session):
        calls["TX"] += 1
        if calls["TX"] >= 3:
            raise KeyboardInterrupt          # end the loop after three cycles
        return good

    monkeypatch.setitem(feeds.ADAPTERS, "TX", txf)
    monkeypatch.setitem(feeds.ADAPTERS, "KS", ks)
    monkeypatch.setattr(feeds.time, "sleep", lambda s: None)
    with pytest.raises(KeyboardInterrupt):
        feeds.main(["TX", "KS", "--out", str(tmp_path), "--loop", "120"])
    assert calls == {"TX": 3, "KS": 1}       # KS asked once, then left alone for ELECTION_BLOCKED_RETRY_S


def test_oh_structure_2026_general():
    r = oh.parse(raw("oh_2026gen_test_vssc1622.xml.gz"), allow_test=True)
    assert_schema(r, "OH", 88)
    assert {c["key"]: c["party"] for c in r["candidates"]} == {
        "brown": "DEM", "husted": "REP", "levy": "OTH", "redpath": "LIB"}   # zero write-ins are not shown
    assert r["precincts"]["reporting"] == 0 and r["precincts"]["total"] > 8000
    fr = next(u for u in r["units"] if u["id"] == "39049")
    assert fr["name"] == "Franklin" and fr["precincts"]["total"] > 800
    assert r["source_updated_at"] == "2026-11-02T01:18:27Z"


def test_oh_aggregation_with_synthetic_counts():
    """The only published file has zeros, so fill in made-up counts (test only) and check the arithmetic."""
    root = etree.fromstring(raw("oh_2026gen_test_vssc1622.xml.gz"))
    root.set("IsTest", "false")
    state_id = next(g.get("ObjectId") for g in root.iter("{*}GpUnit") if g.get("Type") == "State")
    for i, bs in enumerate(root.iter("{*}BallotSelection")):
        tot = 0
        vcs = list(bs.iter("{*}VoteCounts"))
        for j, vc in enumerate(vcs):
            if vc.findtext("{*}GpUnitId").strip() != state_id:
                vc.set("Count", str((i + 1) * 10 + j))
                tot += (i + 1) * 10 + j
        next(vc for vc in vcs if vc.findtext("{*}GpUnitId").strip() == state_id).set("Count", str(tot))
    r = oh.parse(etree.tostring(root))
    assert "writein" in {c["key"] for c in r["candidates"]}
    assert r["total_votes"] == sum(u["total"] for u in r["units"])


# ---------------------------------------------------------------- MI

def test_mi_election_discovery_and_no_guessing():
    html = raw("mi_mvic_index_election_select.html").decode()
    assert mi.discover_election_id(html, "11/5/2024") == 699
    assert mi.discover_election_id(html, "8/6/2024") == 698
    with pytest.raises(C.NotPublished):
        mi.discover_election_id(html, "11/3/2026")
    with pytest.raises(C.ParseError):
        mi.parse_county_records(b"<table></table>")
    with pytest.raises(C.SourceBlocked):
        mi.fetch(FakeSession({"mvic.sos.state.mi.us": CF_CHALLENGE}))


# ---------------------------------------------------------------- CLI

def test_registry_and_cli(tmp_path, monkeypatch):
    assert set(feeds.ADAPTERS) == {"TX", "AK", "KS", "ME", "OH", "MI"}
    good = tx.parse(js("tx_58315_election.json"), js("tx_58315_countyinfo.json.gz"))

    def boom(session):
        raise C.SourceBlocked("challenge")

    monkeypatch.setitem(feeds.ADAPTERS, "TX", lambda session: good)
    monkeypatch.setitem(feeds.ADAPTERS, "KS", boom)
    (tmp_path / "KS.json").write_text('{"old": true}')
    rc = feeds.main(["TX", "KS", "--out", str(tmp_path)])
    assert rc == 1
    assert json.loads((tmp_path / "TX.json").read_text())["total_votes"] == 1391634
    assert json.loads((tmp_path / "KS.json").read_text()) == {"old": True}    # last good file kept

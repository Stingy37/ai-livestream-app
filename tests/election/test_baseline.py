"""Offline checks for the election-night static baseline: data/election/baseline/<ST>.json, the page geometry in
html/election/geo/, and data/election/senate_holdovers.json. See docs/ELECTION.md and research/election/baseline.md.

Reference totals below are the certified statewide results as compiled by the FEC ("Official 2024 Presidential
General Election Results"; "Federal Elections 2020" and "Federal Elections 2022"), which match each state's own
certified canvass.
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "data" / "election" / "baseline"
GEO = REPO / "html" / "election" / "geo"
HOLDOVERS = REPO / "data" / "election" / "senate_holdovers.json"

STATES = ["TX", "AK", "KS", "ME", "OH", "MI"]
FIPS = {"TX": "48", "AK": "02", "KS": "20", "ME": "23", "OH": "39", "MI": "26"}
UNIT_COUNT = {"TX": 254, "KS": 105, "OH": 88, "MI": 83, "ME": 16, "AK": 40}

# certified 2024 presidential totals: (Harris, Trump, total votes)
PRES2024 = {
    "TX": (4835250, 6393597, 11388674),
    "AK": (140026, 184458, 338177),
    "KS": (544853, 758802, 1327591),
    "ME": (435652, 377977, 831375),
    "OH": (2533699, 3180116, 5767788),
    "MI": (2736533, 2816636, 5664186),
}
# certified previous election for the seat up in 2026: (year, dem, rep, total, winner)
SEN_PREV = {
    "TX": (2020, 4888764, 5962983, 11144040, "REP"),  # Hegar / Cornyn
    "AK": (2020, 146068, 191112, 354587, "REP"),  # Gross (independent, Democratic nominee) / Sullivan
    "KS": (2020, 571530, 727962, 1367755, "REP"),  # Bollier / Marshall
    "ME": (2020, 347223, 417645, 819183, "REP"),  # Gideon / Collins, first round
    "MI": (2020, 2734568, 2642233, 5479720, "DEM"),  # Peters / James
    "OH": (2022, 1939489, 2192114, 4133342, "REP"),  # Ryan / Vance
}
VOTE_KEYS = ("dem", "rep", "other", "total")
MEASURES = ("pres2024", "sen_prev")
US_STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR "
    "PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=STATES)
def st(request):
    return request.param


@pytest.fixture(scope="module")
def base(st):
    return load(BASE / f"{st}.json")


@pytest.fixture(scope="module")
def geo(st):
    return load(GEO / f"{st}.json")


# ---------------------------------------------------------------- baseline


def test_baseline_header(st, base):
    assert base["state"] == st
    assert base["fips"] == FIPS[st]
    assert base["unit_type"] == ("house_district" if st == "AK" else "county")
    assert isinstance(base["name"], str) and base["name"]


def test_unit_ids_and_counts(st, base):
    ids = [u["id"] for u in base["units"]]
    assert len(ids) == UNIT_COUNT[st]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
    if st == "AK":
        assert ids == [f"AK-HD{n:02d}" for n in range(1, 41)]
    else:
        assert all(re.fullmatch(r"\d{5}", i) and i.startswith(FIPS[st]) for i in ids)


def test_vote_blocks_consistent(base):
    blocks = [base["statewide"][m] for m in MEASURES]
    blocks += [u[m] for u in base["units"] for m in MEASURES]
    for b in blocks:
        assert all(isinstance(b[k], int) and b[k] >= 0 for k in VOTE_KEYS), b
        assert b["dem"] + b["rep"] + b["other"] == b["total"], b
    for u in base["units"]:
        assert isinstance(u["turnout2022"], int) and u["turnout2022"] > 0, u["id"]
        assert u["name"], u["id"]


def test_unit_sums_equal_statewide(st, base):
    """sum(units) + not_in_units == statewide, exactly; any remainder must be explained."""
    rest = base.get("not_in_units") or {}
    if rest:
        assert len(rest.get("note", "")) > 20, "not_in_units needs an explanation"
    sw = base["statewide"]
    for m in MEASURES:
        for k in VOTE_KEYS:
            units = sum(u[m][k] for u in base["units"])
            assert units + (rest.get(m) or {}).get(k, 0) == sw[m][k], (st, m, k)
    assert sum(u["turnout2022"] for u in base["units"]) + rest.get("turnout2022", 0) == sw["turnout2022"]


def test_statewide_2024_matches_certified(st, base):
    p = base["statewide"]["pres2024"]
    assert (p["dem"], p["rep"], p["total"]) == PRES2024[st]
    assert p["dem_name"] == "Kamala Harris" and p["rep_name"] == "Donald Trump"


def test_statewide_previous_senate_matches_certified(st, base):
    s = base["statewide"]["sen_prev"]
    assert (s["year"], s["dem"], s["rep"], s["total"], s["winner"]) == SEN_PREV[st]
    assert s["dem_name"] and s["rep_name"]
    if st == "AK":
        assert "Gross" in s["dem_name"] and "independent" in s["note"].lower()


def test_turnout2022_plausible(st, base):
    """2022 ballots (or governor votes) vs 2024 presidential votes: a midterm is ~55-90% of a presidential year."""
    t = base["statewide"]["turnout2022"]
    assert 0.55 < t / base["statewide"]["pres2024"]["total"] < 0.9


def test_sources_recorded(base):
    srcs = base["sources"]
    for what in ("pres2024", "sen_prev", "turnout2022"):
        hits = [s for s in srcs if s["what"].startswith(what)]
        assert hits, what
        assert all(s["publisher"] and s["url"].startswith("http") for s in hits)


# ---------------------------------------------------------------- geometry


def rings_of(geom):
    assert geom["type"] in ("Polygon", "MultiPolygon")
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def signed_area(ring):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:])) / 2


def check_features(fc):
    assert fc["type"] == "FeatureCollection"
    for f in fc["features"]:
        assert f["type"] == "Feature"
        for poly in rings_of(f["geometry"]):
            for j, ring in enumerate(poly):
                assert len(ring) >= 4 and ring[0] == ring[-1]
                for x, y in ring:
                    assert -180 <= x <= 180 and 18 <= y <= 72
                    assert round(x, 4) == x and round(y, 4) == y
                # d3-geo winding: exterior rings clockwise, holes counter-clockwise
                a = signed_area(ring)
                assert (a < 0) if j == 0 else (a > 0), (f["properties"]["id"], j)


def test_geometry_matches_baseline_units(st, base, geo):
    by_id = {f["properties"]["id"]: f["properties"] for f in geo["features"]}
    assert len(by_id) == len(geo["features"])
    units = {u["id"]: u["name"] for u in base["units"]}
    assert set(by_id) == set(units), set(by_id) ^ set(units)
    for uid, name in units.items():
        assert by_id[uid]["name"] == name


def test_state_geometry_valid(st, geo):
    size_kb = (GEO / f"{st}.json").stat().st_size / 1024
    assert 20 < size_kb < 600, size_kb
    check_features(geo)


def test_us_states_geometry():
    path = GEO / "us-states.json"
    assert path.stat().st_size < 1_000_000
    fc = load(path)
    props = [f["properties"] for f in fc["features"]]
    ids = {p["id"] for p in props}
    assert ids == US_STATES | {"DC"} and len(props) == 51
    for p in props:
        assert re.fullmatch(r"\d{2}", p["fips"]) and p["name"]
    assert {p["id"]: p["fips"] for p in props if p["id"] in FIPS} == FIPS
    check_features(fc)


# ---------------------------------------------------------------- senate holdovers


def test_senate_holdovers():
    h = load(HOLDOVERS)
    c = h["composition"]
    assert c["R"] + c["D"] + c["I"] + c["vacant"] == c["total"] == 100
    assert h["holdovers"]["seats"] == 65 and h["up_in_2026"]["seats"] == 35
    assert sorted(h["up_in_2026"]["special"]) == ["FL", "OH"]
    assert set(h["by_state"]) == US_STATES
    tally = {"R": 0, "D": 0, "I": 0}
    for st, e in h["by_state"].items():
        assert len(e["senators"]) + len(e["up_in_2026"]) == 2, st
        for p in tally:
            n = sum(s["party"] == p for s in e["senators"])
            assert e[p] == n, (st, p)
            tally[p] += n
        assert all(s["class"] != "II" for s in e["senators"]), st
    assert tally == {k: h["holdovers"][k] for k in tally}
    for p in ("R", "D", "I"):
        up = sum(s["party"] == p for e in h["by_state"].values() for s in e["up_in_2026"])
        assert tally[p] + up == c[p] and up == h["up_in_2026"][p]
    for st in STATES:  # each featured state has exactly one seat on the ballot
        assert len(h["by_state"][st]["up_in_2026"]) == 1
    assert h["by_state"]["OH"]["up_in_2026"][0]["race"] == "special"
    assert h["sources"]

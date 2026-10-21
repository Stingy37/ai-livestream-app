"""Offline tests for the desk data pipeline: parsers on saved agency responses, grounding checks,
stale fallback, validation, and the EC2 desk endpoints (server.py over plain http)."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from desk import geo, sources as S
from desk.build import build_desk, validate
from desk.text import Source, check_item, country_text

FX = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]


def fx(name):
    return (FX / name).read_text(encoding="utf-8", errors="ignore")


def raw_fixture(**overrides):
    raw = {
        "jma": S.parse_jma(json.loads(fx("jma_specifications.json")), json.loads(fx("jma_forecast.json")), "TC2636"),
        "jtwc": S.parse_jtwc(fx("jtwc.tcw"), fx("jtwc_web.txt"), "wp2926"),
        "pagasa": S.parse_pagasa(fx("pagasa_swb.html")),
        "cwa": S.parse_cwa(fx("cwa_ty_news_data.js"), "CHAMPI"),
        "ensemble": {"runUTC": "2026-10-19T18:00:00Z", "errors": [], "sets": [
            {"key": "g", "name": "GEFS", "color": "#ff9a1f", "mean_id": "aemn", "runUTC": "2026-10-19T18:00:00Z", "url": "x",
             "members": [{"id": "ap01", "pts": S.parse_atcf(fx("gefs_ap01.trackatcfunix"), "WP", "29")}]}]},
        "jtwc_id": "wp2926", "jma_tc": "TC2636", "fetched_at": "2026-10-20T03:00:00Z",
    }
    raw.update(overrides)
    return raw


# ---- parsers ---------------------------------------------------------------------------------

def test_jma_parser():
    j = S.parse_jma(json.loads(fx("jma_specifications.json")), json.loads(fx("jma_forecast.json")), "TC2636")
    a = j["analysis"]
    assert (j["name_en"], j["number"]) == ("Champi", "2630")
    assert (a["lat"], a["lon"], a["pressure_hpa"], a["wind_kt"], a["course"]) == (16.0, 135.6, 945.0, 100.0, "WNW")
    assert (a["stormRadiusKm"], a["galeRadiusKm"]) == (165, 650)
    assert [f["hours"] for f in j["forecasts"]] == [12, 24, 48, 72, 96, 120]
    assert j["forecasts"][0]["label"] == "Violent" and j["forecasts"][-1]["label"] == "Severe trop. storm"
    assert len(j["track"]) > 10


def test_jtwc_parser_and_rss():
    t = S.parse_jtwc(fx("jtwc.tcw"), fx("jtwc_web.txt"), "wp2926")
    assert (t["number"], t["name"], t["title"], t["wind_kt"], t["gust_kt"]) == ("29W", "CHAMPI", "SUPER TYPHOON", 130.0, 160.0)
    assert (t["lat"], t["lon"], t["course_deg"], t["speed_kt"]) == (15.9, 135.6, 295.0, 12.0)
    assert len(t["past"]) == 36 and t["past"][-1]["timeUTC"] == "2026-10-20T00:00:00Z"
    assert len({p["timeUTC"] for p in t["past"]}) == 36            # the tcw repeats each fix 3 times
    assert S.parse_jtwc_rss(fx("jtwc.rss")) == [{"id": "wp2926", "number": "29W", "name": "CHAMPI", "title": "SUPER TYPHOON", "warning": 23}]


def test_pagasa_bulletin_and_no_bulletin():
    p = S.parse_pagasa(fx("pagasa_swb.html"))
    assert p["active"] and p["local_name"] == "Rosal" and p["bulletin_no"] == "1"
    assert p["issuedUTC"] == "2026-10-20T03:00:00Z"
    assert (p["wind_kmh"], p["gust_kmh"], p["course"], p["speed_kmh"]) == (185.0, 230.0, "WNW", 25.0)
    assert p["highest_possible"] == [2, 3]
    assert p["signals"][0]["level"] == 1 and p["signals"][0]["areas"]["Luzon"].startswith("Batanes")
    assert "Visayas" not in p["signals"][0]["areas"]                  # "-" means none
    assert S.parse_pagasa(fx("pagasa_tca.html"))["active"] is False


def test_cwa_parser():
    c = S.parse_cwa(fx("cwa_ty_news_data.js"), "CHAMPI")
    assert (c["name_zh"], c["lat"], c["lon"], c["pressure_hpa"], c["wind_ms"], c["gust_ms"], c["course"]) == \
        ("薔琵", 16.0, 135.6, 910.0, 55.0, 68.0, "WNW")
    assert c["timeUTC"] == "2026-10-20T00:00:00Z"


def test_atcf_parser_12_hourly():
    pts = S.parse_atcf(fx("gefs_ap01.trackatcfunix"), "WP", "29")
    assert pts[0] == [15.6, 136.8] and len(pts) >= 10
    assert S.parse_atcf(fx("gefs_ap01.trackatcfunix"), "EP", "29") == []


def test_cpa_and_passes():
    track = [{"lat": 16.0, "lon": 135.6, "timeUTC": "2026-10-20T00:00:00Z"}, {"lat": 24.5, "lon": 123.0, "timeUTC": "2026-10-23T12:00:00Z"}]
    cpa = geo.cpa_table(track)
    assert cpa[0]["city"] == "Yonaguni" and cpa[0]["km"] < 5
    p = geo.passes_by_country(cpa)
    assert len(p["JP"]) == 2 and len(p["TW"]) == 2 and len(p["PH"]) == 2


# ---- grounding checks -------------------------------------------------------------------------

SRC = {"S1": Source("S1", "PAGASA", "u", "", "Wind Signal No. 1 is now hoisted over Batanes. Sea travel is risky.")}


@pytest.mark.parametrize("item, ok", [
    ({"text": "Signal No. 1 over Batanes", "source": "S1", "quote": "Wind Signal No. 1 is now hoisted over Batanes."}, True),
    ({"text": "Signal No. 2 over Batanes", "source": "S1", "quote": "Wind Signal No. 1 is now hoisted over Batanes."}, False),   # number
    ({"text": "Signal over Batanes", "source": "S1", "quote": "Wind Signal No. 3 is now hoisted over Batanes."}, False),         # not in source
    ({"text": "No warnings for Batanes", "source": "S1", "quote": "Wind Signal No. 1 is now hoisted over Batanes."}, False),     # absence
    ({"text": "Evacuations ordered", "source": "S1", "quote": "Sea travel is risky."}, False),                                   # critical term
    ({"text": "Sea travel risky", "source": "S9", "quote": "Sea travel is risky."}, False),                                     # unknown source
])
def test_check_item(item, ok):
    assert (check_item(item, SRC, ("text",)) is None) == ok


def test_country_text_keeps_only_grounded_items():
    reply = json.dumps({"level": "hot",
                        "status": {"text": "Signal No. 1 raised", "source": "S1", "quote": "Wind Signal No. 1 is now hoisted"},
                        "warning": {"text": "Evacuations ordered in Batanes", "source": "S1", "quote": "hoisted over Batanes"},
                        "chips": [{"icon": "wave", "label": "Sea travel", "value": "risky", "source": "S1", "quote": "Sea travel is risky."},
                                  {"icon": "rain", "label": "Rain", "value": "500 mm", "source": "S1", "quote": "Sea travel is risky."}],
                        "ticker": []})
    r = country_text(lambda s, u: reply, "Typhoon Champi", "Philippines", "PAGASA", list(SRC.values()))
    assert r.items["status"]["text"] == "Signal No. 1 raised"
    assert r.items["warning"] is None                                    # invented evacuation dropped
    assert [c["label"] for c in r.items["chips"]] == ["Sea travel"]     # invented 500 mm dropped
    assert r.items["level"] == "hot" and len(r.dropped) == 2


# ---- builder: stale fallback and validation ----------------------------------------------------

def test_build_numbers_only():
    doc, rep = build_desk(None, storm_hint="CHAMPI", ask=None, raw=raw_fixture())
    assert validate(doc) == []
    assert doc["storm"]["names"].startswith("Philippines: Rosal · Taiwan: 薔琵 · Japan: 台風30号")
    assert [a["agency"] for a in doc["agencies"]] == ["JMA", "PAGASA", "CWA", "JTWC"]
    assert doc["agencies"][0]["winds"] == "185 km/h" and doc["agencies"][3]["sub"] == "1-min"
    assert doc["forecast"]["points"][0]["radiusKm"] == 45 and doc["center"]["source"] == "JMA analysis"
    assert doc["ticker"][-1][0] == "SAFETY" and doc["stale"] == []


def test_failed_source_keeps_previous_section():
    prev, _ = build_desk(None, storm_hint="CHAMPI", ask=None, raw=raw_fixture())
    doc, rep = build_desk(prev, storm_hint="CHAMPI", ask=None, raw=raw_fixture(jma=RuntimeError("JMA down"), ensemble=RuntimeError("NOMADS down")))
    assert doc["forecast"] == prev["forecast"] and "forecast" in doc["stale"]
    assert doc["ensemble"] == prev["ensemble"] and "ensemble" in doc["stale"]
    assert doc["provenance"]["forecast"]["ok"] is False and "JMA down" in doc["provenance"]["forecast"]["error"]
    assert doc["center"]["source"] == "JTWC warning"                    # center falls back to JTWC
    assert validate(doc) == []


def test_validate_catches_bad_values():
    doc, _ = build_desk(None, storm_hint="CHAMPI", ask=None, raw=raw_fixture())
    doc["center"]["lat"] = 123
    doc["forecast"]["points"].reverse()
    p = validate(doc)
    assert any("center" in x for x in p) and any("time order" in x for x in p)


# ---- EC2 server endpoints ----------------------------------------------------------------------

def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def server(tmp_path):
    port = _free_port()
    env = dict(os.environ, NO_TLS="1", API_TOKEN="t0ken", DATA_DIR=str(tmp_path / "data"), WEB_DIR=str(tmp_path),
               BIND="127.0.0.1", PORT=str(port))
    proc = subprocess.Popen([sys.executable, str(REPO / "ec2" / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield base, tmp_path / "data"
    proc.terminate()
    proc.wait(5)


def _req(url, data=None, token=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, method="POST" if data is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_server_desk_endpoints(server):
    base, data_dir = server
    assert _req(base + "/live/desk.json")[0] == 204                  # nothing published yet
    doc, _ = build_desk(None, storm_hint="CHAMPI", ask=None, raw=raw_fixture())
    assert _req(base + "/api/v1/desk", doc)[0] == 401                 # no token
    st, body = _req(base + "/api/v1/desk", doc, "t0ken")
    assert st == 200 and json.loads(body)["ok"]
    bad = dict(doc, center={"lat": 999, "lon": 0})
    assert _req(base + "/api/v1/desk", bad, "t0ken")[0] == 422        # invalid: rejected ...
    st, body = _req(base + "/live/desk.json")
    assert st == 200 and json.loads(body)["center"] == doc["center"]   # ... and the good one is still served
    (data_dir / "desk.json").unlink()                                  # main file lost: newest history copy is served
    assert json.loads(_req(base + "/live/desk.json")[1])["generated_at"] == doc["generated_at"]

"""Offline tests for the India desk (DESK_REGION=nio): the PDF text extractor, IMD's bulletin and advisory parsers,
IMD district warnings, JTWC's IO past track, and the builder with a failed source. Fixtures are real responses for
Cyclone Arnab (26 Oct 2026); the National Bulletin and RSMC advisory are stored as their extracted text."""

import json
from datetime import date
from pathlib import Path

from desk import sources as S, sources_nio as N
from desk.build_nio import build_desk_nio, validate_nio
from desk.pdftext import pdf_text

FX = Path(__file__).parent / "fixtures"


def fx(name):
    return (FX / name).read_text(encoding="utf-8", errors="ignore")


def raw_fixture(**overrides):
    imd = N.parse_national(fx("imd_national_bulletin.txt"))
    imd["source_url"] = "https://rsmcnewdelhi.imd.gov.in/uploads/national.pdf"
    imd["_rsmc"] = N.parse_rsmc(fx("imd_rsmc_advisory.txt"))
    imd["_tcac"] = N.parse_tcac(pdf_text((FX / "imd_tcac.pdf").read_bytes()))
    jt = S.parse_jtwc(fx("jtwc_io0226.tcw"), fx("jtwc_io0226web.txt"), "io0226")
    jt["past"] = N.jtwc_past(fx("jtwc_io0226.tcw"))
    raw = {"jtwc_id": "io0226", "jtwc": jt, "imd": imd, "districts": N.parse_districts(json.loads(fx("imd_district_warnings.json")), today=date(2026, 10, 26)),
           "fetched_at": "2026-10-26T15:00:00Z"}
    raw.update(overrides)
    return raw


def test_pdf_text_reads_imd_tcac():
    t = pdf_text((FX / "imd_tcac.pdf").read_bytes())
    for want in ("TCAC: NEW DELHI", "TC: ARNAB", "PSN: N1524 E08854", "MAX WIND: 35KT"):
        assert want in t, want
    assert N.parse_tcac(t) == {"timeUTC": "2026-10-26T00:00:00Z", "pressure_hpa": 1000.0, "wind_kt": 35}


def test_rsmc_links():
    links = N.rsmc_links(fx("imd_rsmc_home.html"))
    assert "National_Bulletin_No_11" in links["national"] and links["national"].startswith(N.RSMC)
    assert links["track_png"].endswith(".png") and "TC_ADVISORY" in links["tcac"]
    assert "Arnab" in links["subject"]


def test_national_bulletin():
    imd = N.parse_national(fx("imd_national_bulletin.txt"))
    assert (imd["bulletin"], imd["issuedUTC"], imd["observedUTC"], imd["message"]) == \
        ("National Bulletin No. 11 (BOB/08/2026)", "2026-10-26T11:30:00Z", "2026-10-26T09:00:00Z", "red")
    assert (imd["class"], imd["class_short"], imd["lat"], imd["lon"]) == ("Cyclonic Storm", "CS", 15.5, 87.8)
    assert imd["movement"] == {"dir": "WNW", "kmh": 13, "hours": 6}
    assert imd["position"][1] == {"km": 540, "dir": "ESE", "place": "Vishakhapatnam", "state": "Andhra Pradesh"}
    assert (imd["wind_kmh"], imd["gust_kmh"]) == ([85, 95], 105)
    land = imd["landfall"]
    assert (land["between"], land["near"], land["class_short"], land["wind_kmh"], land["gust_kmh"], land["date"], land["part_of_day"]) == \
        (["Bapatla", "Visakhapatnam"], "Yanam", "VSCS", [115, 125], 140, "2026-10-28", "forenoon")
    assert len(imd["forecast"]) == 11 and imd["forecast"][0]["timeUTC"] == "2026-10-26T09:00:00Z"
    assert imd["forecast"][6] == {"timeUTC": "2026-10-28T06:00:00Z", "lat": 16.9, "lon": 82.1, "wind_kmh": [115, 125], "gust_kmh": 140,
                                  "class": "Very Severe Cyclonic Storm", "class_short": "VSCS"}
    assert {"date": "2026-10-28", "level": "extremely heavy", "areas": ["Costal Andhra Pradesh", "Odisha"]} in imd["rain"]
    assert any(w["kmh"] == [90, 100] and w["areas"] == ["districts of coastal Andhra Pradesh from Krishna to Anakapalli"]
               for w in imd["wind_warnings"])
    assert imd["surge"]["m"] == [1.0, 1.5] and imd["surge"]["peak_areas"] == ["East Godavari", "Yanam"]
    assert imd["fishermen"]["until"] == "2026-10-29" and len(imd["fishermen"]["items"]) == 5
    assert imd["next_bulletin"]["timeUTC"] == "2026-10-26T15:00:00Z"
    assert len(imd["by_state"]["Tamil Nadu"]) == 3 and all("Tamil Nadu" in s for s in imd["by_state"]["Tamil Nadu"])
    assert not any(s.endswith("..") for s in imd["outlook_text"])


def test_rsmc_advisory():
    assert N.parse_rsmc(fx("imd_rsmc_advisory.txt")) == {"landfall_timeUTC": "2026-10-28T06:00:00Z", "pressure_hpa": 999.0, "pressure_wind_kt": 35}


def test_district_days_follow_ist_midnight():
    """IMD's layer moves its Day columns at midnight IST but keeps the issue date: Day1 is today once the issue date is past."""
    doc = json.loads(fx("imd_district_warnings.json"))
    assert N.parse_districts(doc, today=date(2026, 10, 27))["days"] == ["2026-10-27", "2026-10-28", "2026-10-29"]
    assert N.parse_districts(doc, today=date(2026, 10, 26))["days"] == ["2026-10-26", "2026-10-27", "2026-10-28"]


def test_district_warnings():
    d = N.parse_districts(json.loads(fx("imd_district_warnings.json")), today=date(2026, 10, 26))
    assert d["days"] == ["2026-10-26", "2026-10-27", "2026-10-28"] and d["issued"] == "2026-10-26 0600 UTC"
    assert len(d["states"]["Andhra Pradesh"]) == 26 and len(d["states"]["Tamil Nadu"]) == 38
    kak = d["states"]["Andhra Pradesh"]["Kakinada"]
    assert [c["colour"] for c in kak] == ["yellow", "red", "red"] and "Extremely heavy rain" in kak[1]["hazards"]
    assert N.district_name("SPSR NELLORE") == "SPSR Nellore" and N.district_name("EAST GODAVARI") == "East Godavari"


def test_jtwc_io_past_track():
    past = N.jtwc_past(fx("jtwc_io0226.tcw"))
    assert len(past) == 20 and past[0] == {"timeUTC": "2026-10-21T18:00:00Z", "lat": 11.8, "lon": 88.7, "wind_kt": 20.0}
    assert past[-1]["timeUTC"] == "2026-10-26T12:00:00Z" and past[-1]["wind_kt"] == 80.0


def test_build_nio():
    doc, rep = build_desk_nio(None, storm_hint="ARNAB", raw=raw_fixture())
    assert validate_nio(doc) == [] and rep["fresh"] == ["storm", "center", "forecast", "past", "agencies", "in"]
    assert doc["center"] == {"lat": 15.5, "lon": 87.8, "timeUTC": "2026-10-26T09:00:00Z", "source": "IMD"}
    assert doc["storm"]["names"] == "IMD: Arnab (Ornab) · JTWC: 02B" and doc["storm"]["imd_class_short"] == "CS"
    assert [a["agency"] for a in doc["agencies"]] == ["IMD", "JTWC"] and doc["agencies"][0]["winds"] == "85-95 km/h"
    imd = doc["in"]["imd"]
    assert imd["landfall"]["timeUTC"] == "2026-10-28T06:00:00Z" and imd["landfall"]["time_basis"].startswith("IMD RSMC advisory")
    assert "pressure_hpa" not in imd and not any(k.startswith("_") for k in imd)     # the 999 hPa beside 35 kt is an old figure
    assert doc["in"]["cpa"][0]["place"] == "Yanam" and doc["in"]["cpa"][0]["km"] < 30
    assert set(doc["in"]["districts"]) == {"Andhra Pradesh", "Tamil Nadu", "Puducherry"}
    assert doc["forecast"]["points"][0]["wind_kmh"] == 95 and doc["forecast"]["points"][0]["label"] == "Cyclonic Storm"


def test_failed_imd_keeps_previous_bulletin_and_falls_back_to_jtwc():
    prev, _ = build_desk_nio(None, storm_hint="ARNAB", raw=raw_fixture())
    doc, rep = build_desk_nio(prev, storm_hint="ARNAB", raw=raw_fixture(imd=RuntimeError("IMD down")))
    assert doc["center"]["source"] == "JTWC" and doc["forecast"]["source"].startswith("JTWC")
    assert doc["in"]["imd_stale"] and doc["in"]["imd"]["bulletin"] == prev["in"]["imd"]["bulletin"]
    assert validate_nio(doc) == []


def test_national_bulletin_after_landfall():
    """IMD 0730 IST 3 Nov 2026: the crossing is reported in the past tense, inside the position paragraph."""
    t = ("NATIONAL BULLETIN NO. 20 (BOB/09/2026)\nTIME OF ISSUE: 0730 HOURS IST DATED: 03.11.2026\n\n"
         "The Severe Cyclonic Storm “Murasu” over Westcentral Bay of Bengal close to south Andhra Pradesh coast moved "
         "north-northwestwards with a speed of 08 kmph during past 06 hours, crossed south Andhra Pradesh coast between Nellore and "
         "Narasapur close to Ongole (near Latitude 15.53°N and Longitude 80.22°E) during 0330 to 0530 hours IST with the wind speed "
         "of 100-110 kmph gusting to 120 kmph, and lay centered at 0530 hours IST.\n\n")
    lf = N.parse_national(t)["landfall"]
    assert lf["crossed"] and lf["between"] == ["Nellore", "Narasapur"] and lf["near"] == "Ongole"
    assert (lf["crossed_ist"], lf["date"], lf["timeUTC"]) == (["0330", "0530"], "2026-11-03", "2026-11-03T00:00:00Z")
    assert lf["wind_kmh"] == [100, 110] and lf["gust_kmh"] == 120

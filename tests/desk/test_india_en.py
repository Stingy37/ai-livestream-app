"""Offline tests for the English India stream (saved_configs/india_en.json): the in_en_* narration composed from IMD's
bulletin, the Indian English voice's text normalisation, its audio-stage hook (model faked), and the config."""

import re
import sys
from pathlib import Path
from unittest import mock

import numpy as np

from desk import bulletin
from desk.build_nio import build_desk_nio
from test_nio import raw_fixture

ROOT = Path(__file__).resolve().parents[2]


def _doc(storm="ARNAB"):
    doc, _ = build_desk_nio(None, storm_hint=storm, raw=raw_fixture())
    return doc


def _say(template, doc):
    with mock.patch.object(bulletin, "_in_today", return_value="2026-10-26"):
        return bulletin.build(template, doc)


def test_english_narration_reads_imd_fields():
    doc = _doc()
    now = _say("in_en_now", doc)
    assert "issued at 5:00 pm IST on 26 October" in now
    assert "Cyclonic Storm Arnab is centred about 520 km southeast of Gopalpur" in now
    assert "west-northwestwards at about 13 km/h" in now
    land = _say("in_en_landfall", doc)
    assert "between Bapatla and Visakhapatnam, near Yanam, on the forenoon of 28 October, as a very severe cyclonic storm" in land
    assert "115-125 km/h, gusting to 140 km/h" in land
    warn = _say("in_en_warnings", doc)
    assert "On 27 October, the IMD has issued a red alert for 8 districts, including Anakapalli" in warn
    assert "fishermen" in warn and warn.splitlines()[-1].startswith("For official warnings")
    for text in (now, land, warn, _say("in_en_open", doc), _say("in_en_close", doc)):
        assert not re.search(r"[ఀ-౿஀-௿]", text)          # no Telugu / Tamil script


def test_storm_name_follows_the_desk():
    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    assert _say("in_en_open", doc).startswith("Welcome to our live coverage of Cyclone Murasu.")
    assert "Cyclonic Storm Murasu is centred" in _say("in_en_now", doc)
    doc["in"]["imd"]["class_short"] = "DD"                                    # not named by IMD yet
    assert "The deep depression is centred" in _say("in_en_now", doc)


def test_page_text_has_english():
    assert _doc()["in"]["text"]["en"]["now"][0].startswith("Here is the latest bulletin")


def test_spoken_english():
    from models.tts_indicparler import _sentences, normalise_en

    assert normalise_en("issued at 5:00 pm IST on 26 October.") == \
        "issued at five P M Indian Standard Time on twenty-sixth October."
    assert normalise_en("winds of 85-95 km/h, gusting to 105 km/h") == \
        "winds of eighty-five to ninety-five kilometres per hour, gusting to one hundred and five kilometres per hour"
    assert normalise_en("a surge of 1-1.5 m; 990 hPa") == "a surge of one to one point five metres; nine hundred and ninety hectopascals"
    assert normalise_en("I am told the IMD expects it") == "I am told the I M D expects it"
    long = "word, " * 80 + "end."
    assert all(len(s) <= 262 for line in _sentences(long) for s in line)


def test_delivery_styles():
    from models.tts_indicparler import description

    assert description("Thoma").startswith("Thoma speaks in a clear, confident") and "sense of urgency" in description("Thoma")
    assert description("Thoma:urgent").startswith("Thoma speaks in an urgent, energetic") and "fast pace" in description("Thoma:urgent")
    assert description(None, "en").startswith("Thoma ") and description(None, "te").startswith("Prakash ")


def test_audio_stage_uses_indic_parler(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "src"))
    from audio.audio import AudioGenerator
    from contracts import LLMOutput
    from models import tts_indicparler

    calls = {}

    def fake(text, language, voice=None, device="cuda"):
        calls.update(text=text, language=language, voice=voice)
        return np.zeros(2400, dtype=np.float32), 24000

    monkeypatch.setattr(tts_indicparler, "synthesize", fake)
    scene = mock.Mock(id="sc-now", title="Current Position", language="en", tts_model="indic-parler", tts_voice="Thoma")
    asset = AudioGenerator(tmp_path).synthesize(scene, LLMOutput("Cyclone Murasu is near the coast."))
    assert calls == {"text": "Cyclone Murasu is near the coast.", "language": "en", "voice": "Thoma"}
    assert asset.path.is_file() and asset.duration_seconds == 0.1


def test_english_config_builds():
    from graph import BroadcastGraph

    g = BroadcastGraph.from_config(ROOT / "saved_configs" / "india_en.json")
    assert g.validate().is_valid
    scenes = g.active_scenes()
    assert {s.node_key: s.tts_voice for s in scenes} == {"open": "Thoma", "now": "Thoma", "landfall": "Thoma:urgent",
                                                         "warnings": "Thoma:urgent", "close": "Thoma"}
    assert {(s.language, s.tts_model) for s in scenes} == {("en", "indic-parler")}
    assert {bulletin.template_of(s.sources) for s in scenes} == {"in_en_open", "in_en_now", "in_en_landfall", "in_en_warnings", "in_en_close"}


def test_telugu_and_tamil_say_the_desk_storm():
    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    for template in ("in_te_open", "in_te_now", "in_ta_open", "in_ta_now"):
        text = _say(template, doc)
        assert "అర్నాబ్" not in text and "அர்னாப்" not in text
    assert _say("in_te_open", doc).startswith("మురసు తుఫాను లైవ్ అప్‌డేట్స్.")
    assert _say("in_ta_open", doc).startswith("முரசு புயல் நேரலை.")
    doc["storm"]["name"] = "NEXTSTORM"                                        # not in IN_STORM: no name, never a wrong one
    assert _say("in_te_open", doc).startswith("తుఫాను లైవ్ అప్‌డేట్స్.")


def test_murasu_bulletin_wording():
    """IMD's 0500 IST 2 Nov bulletin for Murasu words things Arnab's did not: "lay centered at 0230 hours IST", "Latitude",
    "moved nearly northwestwards with speed of", "100 to 110 kmph gusting 120 kmph", "(2330 Hrs IST) of 2nd to ... (0400 Hrs IST)"."""
    from desk import sources_nio as N

    imd = N.parse_national((ROOT / "tests" / "desk" / "fixtures" / "imd_national_bulletin_murasu.txt").read_text(encoding="utf-8"))
    assert (imd["class_short"], imd["lat"], imd["lon"], imd["observedUTC"]) == ("SCS", 13.6, 82.5, "2026-11-01T21:00:00Z")
    assert imd["movement"] == {"dir": "NW", "kmh": 20, "hours": 6}
    assert [p["place"] for p in imd["position"]] == ["Chennai", "Nellore", "Machilipatnam", "Kavali", "Ongole", "Vishakhapatnam"]
    lf = imd["landfall"]
    assert (lf["between"], lf["near"], lf["wind_kmh"], lf["gust_kmh"]) == (["Nellore", "Narsapur"], "Ongole", [100, 110], 120)
    assert (lf["date"], lf["time_ist"], lf["timeUTC"], lf["until"]["timeUTC"]) == ("2026-11-02", "2330", "2026-11-02T18:00:00Z",
                                                                                  "2026-11-02T22:30:00Z")
    assert imd["surge"]["peak_areas"] == ["Bapatla", "Krishna", "Prakasam"]
    # the 0900 IST bulletin: "(2330 Hrs IST) of today, the 02nd November to early hours (0400 Hrs IST) of tomorrow, the 3rd"
    t = (ROOT / "tests" / "desk" / "fixtures" / "imd_national_bulletin_murasu.txt").read_text(encoding="utf-8")
    t = t.replace("(2330 Hrs IST) of 2nd to early hours (0400 Hrs IST) of 3rd November,",
                  "(2330 Hrs IST) of today, the 02nd November to early hours (0400 Hrs IST) of tomorrow, the 3rd November,")
    assert "of today, the 02nd" in t
    lf2 = N.parse_national(t)["landfall"]
    assert (lf2["timeUTC"], lf2["until"]["timeUTC"]) == ("2026-11-02T18:00:00Z", "2026-11-02T22:30:00Z")
    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    doc["in"]["imd"].update({k: imd[k] for k in ("class", "class_short", "landfall", "surge")})
    assert ", near Ongole, between 11:30 pm on 2 November and 4 am IST on 3 November, as a severe cyclonic storm." in _say("in_en_landfall", doc)


def test_english_youtube_metadata(tmp_path, monkeypatch):
    """The English stream's title, description and tags: India wording from the thumbnail's lines and IMD's landfall towns,
    with no Philippine typhoon text and no Arnab / Kakinada left over (no YOUTUBE_TITLE needed, so the hourly refresh runs)."""
    import json
    import types

    sys.path.insert(0, str(ROOT / "scripts"))
    monkeypatch.setitem(sys.modules, "broadcast.youtube", types.ModuleType("youtube"))
    import broadcast
    monkeypatch.setattr(broadcast, "youtube", sys.modules["broadcast.youtube"], raising=False)
    import youtube_live

    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    doc["in"]["imd"]["landfall"] = {"between": ["Nellore", "Narsapur"], "near": "Ongole"}
    (tmp_path / "desk.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("THUMB_DESK", str(tmp_path / "desk.json"))
    monkeypatch.setattr(youtube_live, "desk_storm", lambda: {})
    cfg = json.loads((ROOT / "saved_configs" / "india_en.json").read_text(encoding="utf-8"))
    words = json.loads((ROOT / "saved_configs" / "thumb_murasu_en.json").read_text(encoding="utf-8"))
    thumb = {"text": {k: words[k].replace("#GUST", "120").replace("#H", "16") for k in ("l1", "l2")}}
    m = youtube_live.metadata(cfg, "en", thumb)
    assert m["title"].startswith("Cyclone Murasu LIVE 🔴 Heads For Andhra | Winds Up To 120 km/h | Ongole Landfall")
    assert len(m["title"]) <= 100
    assert "between Nellore and Narsapur, near Ongole" in m["description"] and "Ongole cyclone" in m["tags"]
    text = m["title"] + m["description"] + " ".join(m["tags"])
    assert not re.search(r"Arnab|Kakinada|PAGASA|[Tt]yphoon", text)


def test_murasu_1145_landfall_south_of_ongole():
    """IMD 1145 IST 2 Nov: "between Nellore and Narsapur, to the south of Ongole" (no "close to"). The Telugu landfall
    scene was dropped (Narsapur had no Telugu name and there was no "near" town) and the thumbnail lost its marker."""
    from desk import sources_nio as N

    t = (ROOT / "tests" / "desk" / "fixtures" / "imd_national_bulletin_murasu.txt").read_text(encoding="utf-8")
    t = t.replace("between Nellore and Narsapur\nclose to Ongole", "between Nellore and Narsapur,\nto the south of Ongole")
    assert "to the south of Ongole" in t
    lf = N.parse_national(t)["landfall"]
    assert (lf["between"], lf["near"], lf["near_rel"]) == (["Nellore", "Narsapur"], "Ongole", "south")
    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    doc["in"]["imd"]["landfall"] = lf
    te = _say("in_te_landfall", doc)
    assert "నెల్లూరు, నరసాపురం మధ్య ఒంగోలుకు దక్షిణంగా" in te
    assert ", to the south of Ongole," in _say("in_en_landfall", doc)


def test_murasu_2200_surge_en_dash():
    """IMD 2200 IST 2 Nov: "peak surge of 1.0 – 1.5 m" (en dash with spaces) and "areas of South Andhra Pradesh coast
    from evening of today": the surge sentence had dropped out of both landfall scenes."""
    from desk import sources_nio as N

    sec = ("The storm surge of height more than 0.5 m above astronomical tide is likely to inundate low lying areas of South "
           "Andhra Pradesh coast from evening of today, the 2nd November till morning of tomorrow, the 3rd November with peak "
           "surge of 1.0 – 1.5 m above astronomical tides during night of today. The maximum peak surge is expected over "
           "Bapatla, Krishna and Prakasam districts.")
    sg = N._surge(sec)
    assert sg["m"] == [1.0, 1.5] and sg["areas"] == ["South Andhra Pradesh coast"]
    assert sg["peak_areas"] == ["Bapatla", "Krishna", "Prakasam"]
    doc = _doc()
    doc["storm"]["name"] = "MURASU"
    doc["in"]["imd"]["surge"] = sg
    assert "A storm surge of about 1-1.5 m could flood low-lying areas of Bapatla, Krishna and Prakasam." in _say("in_en_landfall", doc)
    assert "1-1.5 మీటర్ల" in _say("in_te_landfall", doc)

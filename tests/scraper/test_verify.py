"""Offline tests for the verify node: quote validation, staleness, conflicts, baseline. No LLM calls."""

import json
from datetime import datetime, timedelta, timezone

from contracts import ScrapedDocument

from scraper.prompts import extract_json
from scraper.verify import (BaselineRule, Claim, VerifyResult, baseline, extract_claims, find_conflicts, is_stale,
                            verify_documents)

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)


def doc(url, text, agency="PAGASA", published=None):
    return ScrapedDocument(url=url, title="t", main_text=text, source_name=agency, published_at=published, fetched_at=NOW, metadata={})


def test_extract_json_is_lenient():
    assert extract_json('<think>hmm</think>Sure:\n```json\n{"a": [1, 2,]}\n```') == {"a": [1, 2]}
    assert extract_json('Thought: x\nAction: {"queries": ["q"], "follow_urls": []}') == {"queries": ["q"], "follow_urls": []}
    assert extract_json("no json here") is None


def test_claims_not_quoted_from_the_text_are_dropped():
    d = doc("u1", "PAGASA said winds of 185 km/h near the center. It moves west at 15 km/h.")
    reply = json.dumps({"claims": [
        {"quote": "winds of 185 km/h near the center", "agency": "PAGASA", "quantity_type": "sustained_wind", "value": "185", "unit": "km/h", "time": ""},
        {"quote": "evacuation ordered in Aparri", "agency": "PAGASA", "quantity_type": "evacuation", "value": "", "unit": "", "time": ""},   # invented
        {"quote": "moves  west at 15 km/h", "agency": "PAGASA", "quantity_type": "movement", "value": "15", "unit": "km/h", "time": ""},   # whitespace differs: still a quote
    ]})
    claims, dropped = extract_claims(d, lambda s, u: reply)
    assert [c.quantity_type for c in claims] == ["sustained_wind", "movement"] and dropped == 1


def test_staleness_uses_hours_and_calendar_day_for_date_only_pages():
    stale, age, _ = is_stale(NOW - timedelta(hours=7), NOW, stale_hours=6)
    assert stale and 6.9 < age < 7.1
    stale, _, _ = is_stale(NOW - timedelta(hours=2), NOW, stale_hours=6)
    assert not stale
    assert is_stale(None, NOW) == (False, None, "no published time on the page")
    today_date_only = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)      # page prints only "20 October 2026"
    assert not is_stale(today_date_only, NOW, stale_hours=6)[0]
    assert is_stale(datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc), NOW, stale_hours=6)[0]


def test_conflicts_only_between_different_agencies_and_comparable_claims():
    claims = [Claim("u1", "PAGASA", "winds of 185 km/h", "PAGASA", "sustained_wind", "185", "km/h"),
              Claim("u2", "JMA", "winds of 230 km/h", "JMA", "sustained_wind", "230", "km/h"),
              Claim("u3", "PAGASA", "winds of 230 km/h", "PAGASA", "sustained_wind", "230", "km/h")]
    reply = json.dumps({"conflicts": [{"pair": 1, "reason": "185 vs 230 km/h"}, {"pair": 9, "reason": "bad index"}]})
    conflicts, calls = find_conflicts(claims, lambda s, u: reply)
    assert calls == 1 and len(conflicts) == 1 and conflicts[0]["a"]["agency"] == "PAGASA" and conflicts[0]["b"]["agency"] == "JMA"
    # a single agency never triggers a conflict call at all
    assert find_conflicts(claims[:1] + claims[2:], lambda s, u: 1 / 0) == ([], 0)


def test_candidate_pair_gating_is_deterministic():
    from scraper.verify import candidate_pairs, numbers_agree
    jtwc = Claim("u1", "JTWC", "135 KT", "JTWC", "sustained_wind", "135", "kt", "2026-10-19T18:00:00Z")
    jma = Claim("u2", "JMA", "50 m/s", "JMA", "sustained_wind", "50", "m/s", "2026-10-20T00:00:00Z")
    pagasa = Claim("u3", "PAGASA", "185 km/h", "PAGASA", "sustained_wind", "185", "km/h", "")
    assert candidate_pairs("sustained_wind", [jtwc, jma]) == []            # 1-minute vs 10-minute winds: expected to differ
    assert numbers_agree("sustained_wind", jma, pagasa)                     # 180 km/h vs 185 km/h: rounding
    assert candidate_pairs("sustained_wind", [jma, pagasa]) == []
    cwa = Claim("u4", "CWA", "230 km/h", "CWA", "sustained_wind", "230", "km/h", "")
    assert candidate_pairs("sustained_wind", [jma, cwa]) == [(jma, cwa)]   # 180 vs 230 km/h: ask the model
    p1 = Claim("u1", "JTWC", "15.4N 136.7E", "JTWC", "position", "", "", "2026-10-19T18:00:00Z")
    p2 = Claim("u2", "JMA", "16.0N 135.6E", "JMA", "position", "", "", "2026-10-20T00:00:00Z")
    p3 = Claim("u3", "PAGASA", "16.1N 135.5E", "PAGASA", "position", "", "", "")
    assert candidate_pairs("position", [p1, p2, p3]) == []                   # 6 h apart, or untimed: not comparable
    p4 = Claim("u4", "JMA", "16.0N 135.6E", "JMA", "position", "", "", "2026-10-19T19:00:00Z")
    assert candidate_pairs("position", [p1, p4]) == [(p1, p4)]
    pr1 = Claim("u1", "JMA", "945 hPa", "JMA", "pressure", "945", "hPa", "")
    pr2 = Claim("u2", "CWA", "948 hPa", "CWA", "pressure", "948", "hPa", "")
    assert candidate_pairs("pressure", [pr1, pr2]) == []
    unit_only = Claim("u5", "World Natural Disasters", "Magnitude Unit | kts", "World Natural Disasters", "sustained_wind", "", "kts", "")
    assert candidate_pairs("sustained_wind", [cwa, unit_only]) == []       # no figure, nothing to conflict with


def test_agency_names_are_canonical_and_ancient_dates_are_ignored():
    from scraper.verify import canonical_agency
    assert canonical_agency("Philippine Atmospheric, Geophysical and Astronomical Services Administration (PAGASA)", "x") == "PAGASA"
    assert canonical_agency("Japan Meteorological Agency", "x") == "JMA" and canonical_agency("", "Philstar") == "Philstar"
    assert is_stale(datetime(1999, 1, 1, 12, 0, tzinfo=timezone.utc), NOW)[0] is False


def test_verify_documents_reuses_previous_claims_and_sets_flags():
    d1 = doc("u1", "JMA reports central pressure 945 hPa at 00 UTC.", "JMA", NOW - timedelta(hours=1))
    d2 = doc("u2", "JTWC reports pressure 930 hPa.", "JTWC", NOW - timedelta(hours=9))
    asked = []

    def ask(system, user):
        asked.append(user)
        if "Quantity:" in user:
            return json.dumps({"conflicts": []})
        if "u1" in user:
            return json.dumps({"claims": [{"quote": "central pressure 945 hPa", "agency": "JMA", "quantity_type": "pressure", "value": "945", "unit": "hPa", "time": "2026-10-20T00:00:00Z"}]})
        return json.dumps({"claims": [{"quote": "pressure 930 hPa", "agency": "JTWC", "quantity_type": "pressure", "value": "930", "unit": "hPa", "time": ""}]})

    first = verify_documents([d1, d2], ask, stale_hours=6)
    assert len(first.claims) == 2 and first.stale_docs["u2"]["stale"] and not first.stale_docs["u1"]["stale"]
    assert [c.stale for c in first.claims] == [False, True]
    n = len(asked)
    second = verify_documents([d1, d2], ask, stale_hours=6, previous=first)   # same docs again: no new claim calls
    assert len(second.claims) == 2 and len(asked) == n + 1   # only the conflict question was asked again
    flags = second.flags_for("u2")
    assert flags["stale"] and flags["claims"] == 1 and flags["conflicts"] == []


def test_baseline_gate_rules():
    d1 = doc("u1", "x", "JMA", NOW)
    v = VerifyResult(claims=[Claim("u1", "JMA", "q", "JMA", "position"), Claim("u1", "JMA", "q", "JMA", "sustained_wind", stale=True)])
    v.stale_docs = {"u1": {"stale": False, "age_hours": 0.5}}
    gate = baseline(["position", "sustained_wind", "agency_attribution", "official_channels"], [d1], v)
    assert not gate["passed"] and gate["missing"] == ["sustained_wind"] and gate["coverage"] == 0.75
    gate = baseline(["position", "agency_attribution", "official_channels"], [d1], v)
    assert gate["passed"]
    v.conflicts = [{"quantity_type": "position", "a": {"doc_url": "u1", "agency": "JMA", "quote": "a"}, "b": {"doc_url": "u2", "agency": "JTWC", "quote": "b"}, "reason": "r"}]
    assert not baseline(["position"], [d1], v)["passed"]
    assert baseline(["position"], [d1], v, BaselineRule(max_conflicts=1))["passed"]

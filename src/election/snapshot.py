"""Snapshots: everything one scene shows, localised for one stream, built from the data on disk at one instant.

    state_snapshot("TX", "ja", now) -> dict      (docs/ELECTION.md "State snapshot")
    national_snapshot("ja", now)    -> dict      ("National snapshot")
    desk("ja", now)                 -> dict      ("desk.json")

Inputs: data/election/races.json, data/election/i18n.json, data/election/baseline/<ST>.json, the feeds' output
output/election/live/<ST>.json and the operator-confirmed AP calls output/election/calls.json. No network, no LLM.

Rules enforced here (research/election/legal.md): nothing about a state's count before its LAST poll closing
(rule 27); counts only from the official state source (rule 8); votes left only as "counted so far vs the 2022
total" (rule 13); a winner only as a confirmed AP declaration (rules 2-7).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "election"
LIVE = Path(os.environ.get("ELECTION_LIVE_DIR", REPO / "output" / "election" / "live"))
CALLS = Path(os.environ.get("ELECTION_CALLS", REPO / "output" / "election" / "calls.json"))
ET = timezone(timedelta(hours=-5))
FEATURED = ["TX", "AK", "KS", "ME", "OH", "MI"]
LIVE_MAX_AGE = timedelta(minutes=30)          # an official file older than this is still shown, but flagged stale

NAME_FIELD = {"es": "name_es", "ja": "name_ja", "zh": "name_zh_hans"}
TXT_FIELD = {"es": "es", "ja": "ja", "zh": "zh_hans"}
RACE_LABEL = {"es": "Senado", "ja": "上院選", "zh": "参议院选举"}
SPECIAL_LABEL = {"es": "Senado (elección especial)", "ja": "上院補欠選", "zh": "参议院补选"}

# surnames for the 2024 presidential and previous-Senate rows (standard renderings in each language's major media)
SURNAME = {
    "Kamala Harris": {"ja": "ハリス", "zh": "哈里斯"}, "Donald Trump": {"ja": "トランプ", "zh": "特朗普"},
    "MJ Hegar": {"ja": "ヘガー", "zh": "赫加尔"}, "John Cornyn": {"ja": "コーニン", "zh": "科宁"},
    "Al Gross": {"ja": "グロス", "zh": "格罗斯"}, "Dan Sullivan": {"ja": "サリバン", "zh": "沙利文"},
    "Barbara Bollier": {"ja": "ボリエ", "zh": "博利尔"}, "Roger Marshall": {"ja": "マーシャル", "zh": "马歇尔"},
    "Sara Gideon": {"ja": "ギデオン", "zh": "吉迪恩"}, "Susan Collins": {"ja": "コリンズ", "zh": "柯林斯"},
    "Tim Ryan": {"ja": "ライアン", "zh": "瑞安"}, "JD Vance": {"ja": "バンス", "zh": "万斯"}, "J.D. Vance": {"ja": "バンス", "zh": "万斯"},
    "Gary Peters": {"ja": "ピーターズ", "zh": "彼得斯"}, "John James": {"ja": "ジェームズ", "zh": "詹姆斯"},
}
SOURCE = {
    "TX": {"es": "Secretaría de Estado de Texas", "ja": "テキサス州務長官室", "zh": "得州州务卿办公室"},
    "AK": {"es": "División de Elecciones de Alaska", "ja": "アラスカ州選挙管理局", "zh": "阿拉斯加州选举处"},
    "KS": {"es": "Secretaría de Estado de Kansas", "ja": "カンザス州務長官室", "zh": "堪萨斯州州务卿办公室"},
    "ME": {"es": "Secretaría de Estado de Maine", "ja": "メーン州務長官室", "zh": "缅因州州务卿办公室"},
    "OH": {"es": "Secretaría de Estado de Ohio", "ja": "オハイオ州務長官室", "zh": "俄亥俄州州务卿办公室"},
    "MI": {"es": "Secretaría de Estado de Michigan", "ja": "ミシガン州務長官室", "zh": "密歇根州州务卿办公室"},
}
RCV_NOTE = {
    "ME": {"es": "Maine vota por orden de preferencia: se muestran primeras preferencias. Para ganar sin recuento por rondas hace falta más del 50 % de todas las papeletas.",
           "ja": "メーン州は順位選択投票：表示は第1希望の票数。全投票の過半数を得る候補がいなければ、後日、順位に基づく集計を実施",
           "zh": "缅因州采用排序复选制：显示的是第一选择票。若无人获得全部选票的过半数，将在日后进行排序计票"},
    "AK": {"es": "Alaska vota por orden de preferencia: se muestran primeras preferencias. Si hace falta, el recuento por rondas será el 18 de noviembre.",
           "ja": "アラスカ州は順位選択投票：表示は第1希望の票数。必要な場合、順位に基づく集計は11月18日の予定",
           "zh": "阿拉斯加州采用排序复选制：显示的是第一选择票。如有需要，排序计票预定于11月18日进行"},
}
CALL_TEXT = {"es": "La agencia AP declaró la victoria de {name}.", "ja": "AP通信は、{name}氏の勝利（当選確実）を伝えました。",
             "zh": "美联社宣布{name}胜选。"}
CREDIT = {"es": "Declaración: The Associated Press (vía {outlet}), {at}", "ja": "勝敗の判定：AP通信（{outlet}経由）{at}",
          "zh": "胜选判定：美联社（经{outlet}）{at}"}


def _load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


_CACHE: dict[str, tuple[float, Any]] = {}


def _cached(path: Path) -> Any:
    """Static inputs re-read only when the file changes (i18n.json may still be filling in)."""
    try:
        m = path.stat().st_mtime
    except OSError:
        return None
    hit = _CACHE.get(str(path))
    if hit and hit[0] == m:
        return hit[1]
    val = _load(path)
    _CACHE[str(path)] = (m, val)
    return val


def races() -> dict:
    return _cached(DATA / "races.json")


def i18n() -> dict:
    return _cached(DATA / "i18n.json") or {"cards": {}, "units": {}, "notes": {}}


def baseline(st: str) -> dict:
    return _cached(DATA / "baseline" / f"{st}.json")


def calls() -> dict:
    """Confirmed AP declarations {ST: {key, url, outlet, at, ...}}; written only by `python -m election.calls confirm`."""
    c = _load(CALLS, {}) or {}
    return {k: v for k, v in (c.get("calls", c) or {}).items() if isinstance(v, dict) and v.get("key") and not v.get("retracted")}


def retracted(st: str) -> bool:
    """AP withdrew a declaration we had relayed (rule 7: say so on air)."""
    c = _load(CALLS, {}) or {}
    v = (c.get("calls", c) or {}).get(st)
    return bool(isinstance(v, dict) and v.get("retracted"))


def live(st: str) -> dict | None:
    d = _load(LIVE / f"{st}.json")
    if not d or d.get("is_test") or d.get("test"):
        return None
    return d


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _pct(a: float, b: float) -> float:
    return round(100.0 * a / b, 1) if b else 0.0


def short_name(full: str, lang: str) -> str:
    if lang == "ja":
        return full.split("・")[-1]
    if lang == "zh":
        return full.split("·")[-1].split("・")[-1]
    parts = [p for p in full.replace(",", " ").split() if p.rstrip(".") not in ("Jr", "Sr", "II", "III")]
    return parts[-1] if parts else full


def cand_name(c: dict, lang: str) -> str:
    return c.get(NAME_FIELD[lang]) or c.get("name") or c.get("key", "?")


def party_label(party: str, lang: str) -> str:
    p = (races().get("parties") or {}).get(party) or {}
    return p.get(TXT_FIELD[lang]) or p.get("en") or party


def state_name(st: str, lang: str) -> str:
    f = races()["featured"].get(st)
    if f:
        return f["state_name"].get(TXT_FIELD[lang]) or f["state_name"]["en"]
    for r in races()["senate_races"]:
        if r["state"] == st:
            return (r.get("state_name_i18n") or {}).get(TXT_FIELD[lang]) or r.get("state_name") or st
    return st


def last_close(st: str) -> datetime:
    f = races()["featured"].get(st)
    if f:
        return _t(f["poll_close"]["last_et"])
    for r in races()["senate_races"]:
        if r["state"] == st:
            return _t(r["poll_close_et"])
    raise KeyError(st)


def main_close(st: str) -> datetime:
    f = races()["featured"].get(st)
    return _t(f["poll_close"]["main_et"]) if f else last_close(st)


def _official_counts(st: str, now: datetime) -> dict | None:
    """The official count for a state, or None before its last poll closing / when there is none."""
    if now < last_close(st):
        return None
    d = live(st)
    if not d or not d.get("total_votes"):
        return None
    return d


def state_snapshot(st: str, lang: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    R = races()
    f = R["featured"][st]
    I = i18n()
    base = baseline(st)
    unit_names = (I.get("units", {}).get(st, {}) or {}).get(lang, {})
    live_d = _official_counts(st, now)
    call = calls().get(st) if now >= last_close(st) else None
    phase = "preview" if now < last_close(st) else ("declared" if call else "counting")

    ballot = {c["key"]: c for c in f["candidates"]}
    order = [c["key"] for c in f["candidates"]]
    cands: list[dict] = []
    total = 0
    if live_d:
        total = int(live_d.get("total_votes") or 0)
        for lc in live_d.get("candidates", []):
            key = lc.get("key")
            rc = ballot.get(key, {})
            name = cand_name(rc, lang) if rc else lc.get("name", key)
            cands.append({"key": key, "name": name, "short": short_name(name, lang), "party": lc.get("party") or rc.get("party", "OTH"),
                          "party_label": party_label(lc.get("party") or rc.get("party", "OTH"), lang), "incumbent": bool(rc.get("incumbent")),
                          "votes": int(lc.get("votes") or 0), "pct": _pct(int(lc.get("votes") or 0), total), "on_card": key in ballot})
        cands.sort(key=lambda c: -c["votes"])
        if len(cands) >= 2:
            cands[0]["ahead_by"] = cands[0]["votes"] - cands[1]["votes"]
            cands[0]["ahead_pts"] = round(cands[0]["pct"] - cands[1]["pct"], 1)
    else:
        for key in order:
            rc = ballot[key]
            name = cand_name(rc, lang)
            cands.append({"key": key, "name": name, "short": short_name(name, lang), "party": rc["party"],
                          "party_label": party_label(rc["party"], lang), "incumbent": bool(rc.get("incumbent")),
                          "votes": None, "pct": None, "on_card": True})
    t22 = int(base["statewide"].get("turnout2022") or 0)

    # units: current count by unit (only with an official count), 2024 history always
    live_units = {u["id"]: u for u in (live_d or {}).get("units", [])}
    rows, hist_units = [], {}
    for u in base["units"]:
        nm = unit_names.get(u["id"], {}) if isinstance(unit_names, dict) else {}
        p24 = u.get("pres2024") or {}
        tot24 = p24.get("total") or 0
        if tot24:
            d, r = _pct(p24.get("dem", 0), tot24), _pct(p24.get("rep", 0), tot24)
            hist_units[u["id"]] = {"winner": "DEM" if d > r else "REP", "margin_pts": round(abs(d - r), 1),
                                   "pres2024": {"dem_pct": d, "rep_pct": r, "total": tot24}}
        row = {"id": u["id"], "name": nm.get("name", u["name"]), "short": nm.get("short", u["name"]),
               "turnout2022": u.get("turnout2022") or 0}
        lu = live_units.get(u["id"])
        if lu and lu.get("total"):
            vs = lu.get("votes", {})
            ranked = sorted(vs.items(), key=lambda kv: -kv[1])
            row.update(total=int(lu["total"]), votes=vs, leader=ranked[0][0] if ranked and ranked[0][1] > 0 else None,
                       margin_pts=round(_pct(ranked[0][1], lu["total"]) - (_pct(ranked[1][1], lu["total"]) if len(ranked) > 1 else 0), 1) if ranked else None,
                       counted_vs_2022_pct=_pct(lu["total"], row["turnout2022"]) if row["turnout2022"] else None,
                       precincts=lu.get("precincts"))
        else:
            row.update(total=0, votes={}, leader=None, margin_pts=None, counted_vs_2022_pct=0.0 if live_d else None)
        rows.append(row)
    big = sorted(rows, key=lambda r: -r["turnout2022"])
    callouts = [r["id"] for r in big[:5]]
    votes_left = [{"id": r["id"], "name": r["name"], "short": r["short"], "counted": r["total"], "total2022": r["turnout2022"],
                   "pct": r.get("counted_vs_2022_pct")} for r in big[:6]] if live_d else []

    sw = base["statewide"]
    p24, sp = sw["pres2024"], sw["sen_prev"]

    def sur(n: str) -> str:
        return SURNAME.get(n, {}).get(lang) or n.split()[-1]

    history = {
        "pres2024": {"dem_name": sur(p24["dem_name"]), "rep_name": sur(p24["rep_name"]), "dem": p24["dem"], "rep": p24["rep"],
                     "dem_pct": _pct(p24["dem"], p24["total"]), "rep_pct": _pct(p24["rep"], p24["total"]), "total": p24["total"]},
        "sen_prev": {"year": sp["year"], "dem_name": sur(sp["dem_name"]), "rep_name": sur(sp["rep_name"]), "dem": sp["dem"], "rep": sp["rep"],
                     "dem_pct": _pct(sp["dem"], sp["total"]), "rep_pct": _pct(sp["rep"], sp["total"]), "total": sp["total"],
                     "dem_is_independent": st == "AK"},
        "turnout2022": t22,
        "units": hist_units,
    }
    notes = (I.get("notes", {}).get(st, {}) or {}).get(lang) or []
    senators = []
    for i, s in enumerate(f["senators"]):
        nm = cand_name(s, lang)
        senators.append({"name": nm, "short": short_name(nm, lang), "party": s.get("caucus") if s["party"] == "IND" else s["party"],
                         "party_raw": s["party"], "party_label": party_label(s["party"], lang),
                         "since": int(str(s.get("in_office_since", "0"))[:4] or 0), "next_election": s.get("next_election_year"),
                         "up": bool(s.get("seat_up_2026")), "running": s.get("running_2026"), "note": notes[i] if i < len(notes) else ""})
    cards = []
    for c in f["candidates"]:
        tr = (I.get("cards", {}).get(st, {}).get(c["key"], {}) or {}).get(lang) or {}
        nm = cand_name(c, lang)
        show_age = c.get("age") if all(x.get("age") for x in f["candidates"]) else None
        cards.append({"key": c["key"], "name": nm, "short": short_name(nm, lang), "party": c["party"], "party_label": party_label(c["party"], lang),
                      "incumbent": bool(c.get("incumbent")), "role": tr.get("role"), "age": show_age,
                      "facts": tr.get("facts") or [], "positions": tr.get("positions") or [], "translated": bool(tr)})
    call_out = None
    if call:
        rc = ballot.get(call["key"], {})
        nm = short_name(cand_name(rc, lang), lang) if rc else call["key"]
        at = call.get("at", "")
        if at.startswith("by "):                     # reported by then; AP gave no time
            t = at[3:]
            at = {"es": f"a más tardar {t}", "ja": f"{t}までに", "zh": f"截至{t}"}[lang]
        call_out = {"key": call["key"], "text": CALL_TEXT[lang].format(name=nm),
                    "credit": CREDIT[lang].format(outlet=call.get("outlet", "apnews.com"), at=at),
                    "url": call.get("url")}
    as_of = (live_d or {}).get("source_updated_at") or (live_d or {}).get("fetched_at")
    try:                       # a source clock in the future (TX labels Central time as UTC) -> our fetch time
        if as_of and live_d and live_d.get("fetched_at") and _t(as_of) > _t(live_d["fetched_at"]) + timedelta(minutes=5):
            as_of = live_d["fetched_at"]
    except ValueError:
        as_of = (live_d or {}).get("fetched_at")
    stale = bool(live_d and live_d.get("fetched_at") and now - _t(live_d["fetched_at"]) > LIVE_MAX_AGE)
    return {
        "state": st, "state_name": state_name(st, lang),
        "race_label": SPECIAL_LABEL[lang] if f["race"].get("special") else RACE_LABEL[lang],
        "special": bool(f["race"].get("special")), "rcv": bool((f.get("rcv") or {}).get("used")),
        "phase": phase,
        "poll_close": {"main_et": f["poll_close"]["main_et"], "last_et": f["poll_close"]["last_et"]},
        "as_of": as_of, "stale": stale, "source": SOURCE[st][lang], "official": bool(live_d),
        "results_available": bool(live_d),
        "candidates": cands, "total_votes": total if live_d else None,
        "precincts": (live_d or {}).get("precincts"),
        "counted_vs_2022": {"counted": total, "total2022": t22, "pct": _pct(total, t22)} if live_d else None,
        "units": {"type": base.get("unit_type", "county"), "geo": f"election/geo/{st}.json", "rows": rows},
        "callouts": callouts, "votes_left": votes_left,
        "history": history, "senators": senators, "cards": cards,
        "call": call_out,
        "rcv_note": RCV_NOTE.get(st, {}).get(lang),
        "lang": lang,
        "test_data": bool(live_d and (live_d.get("synthetic_test_data") or live_d.get("source") == "TEST DATA")),
        "call_retracted": (not call) and now >= last_close(st) and retracted(st),
    }


def race_status(r: dict, now: datetime, C: dict | None = None) -> str:
    st = r["state"]
    if now < last_close(st):
        return "polls_open"
    if st in (calls() if C is None else C):            # one read of calls.json per snapshot (it changes while we run)
        return "declared"
    if st in FEATURED and _official_counts(st, now):
        return "counting"
    return "polls_closed"


def national_snapshot(lang: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    R = races()
    C = calls()
    hold = {"REP": 0, "DEM": 0, "IND": 0}
    for h in R.get("holdovers", []) if isinstance(R.get("holdovers"), list) else []:
        p = h.get("party")
        if p in hold:
            hold[p] += 1
    if not sum(hold.values()):
        hold = {"REP": 31, "DEM": 32, "IND": 2}
    declared = {"REP": 0, "DEM": 0, "IND": 0}
    out_races, sched = [], {}
    for r in R["senate_races"]:
        st = r["state"]
        status = race_status(r, now, C)
        dec = None
        if status == "declared":
            key = C[st]["key"]
            cand = next((n for n in r.get("nominees", []) + r.get("other_candidates", []) if n.get("key") == key), None)
            party = (cand or {}).get("party", "OTH")
            declared[party if party in declared else "IND"] += 1
            nm = cand_name(R["featured"][st]["candidates"][[c["key"] for c in R["featured"][st]["candidates"]].index(key)], lang) \
                if st in R["featured"] and key in [c["key"] for c in R["featured"][st]["candidates"]] else (cand or {}).get("name", key)
            dec = {"party": party, "short": short_name(nm, lang)}
        leader, rows = None, []
        d = _official_counts(st, now) if st in FEATURED and status in ("counting", "declared") else None
        if d and d.get("total_votes"):
            card = {c["key"]: c for c in R["featured"][st]["candidates"]}
            top = sorted(d.get("candidates", []), key=lambda c: -int(c.get("votes") or 0))
            for c in top:
                if c.get("key") not in card:
                    continue
                nm = cand_name(card[c["key"]], lang)
                rows.append({"key": c["key"], "short": short_name(nm, lang), "party": c.get("party") or card[c["key"]]["party"],
                             "pct": _pct(int(c.get("votes") or 0), int(d["total_votes"]))})
            if rows and status == "counting":
                leader = {"party": rows[0]["party"], "short": rows[0]["short"], "pct": rows[0]["pct"]}
        lc = last_close(st)
        out_races.append({"state": st, "state_name": state_name(st, lang), "status": status, "special": bool(r.get("special")),
                          "incumbent_party": (r.get("incumbent") or {}).get("party"), "declared": dec, "featured": st in FEATURED,
                          "poll_close_last_et": lc.astimezone(ET).isoformat(), "leader": leader, "rows": rows})
        sched.setdefault(lc.astimezone(ET).isoformat(), []).append(st)
    schedule = [{"et": k, "states": sorted(v)} for k, v in sorted(sched.items())]
    return {"balance": {"majority": 51, "holdover": hold, "declared": declared,
                        "undecided": len(out_races) - sum(declared.values()), "up": len(out_races)},
            "composition_before": {"REP": 53, "DEM": 45, "IND": 2},
            "races": out_races, "schedule": schedule, "as_of": now.isoformat(timespec="seconds"), "lang": lang,
            # chamber control as reported by AP (operator-written output/election/control.json; relayed, never inferred)
            "control": (_load(CALLS.parent / "control.json", {}) or {}).get("senate")}


STRIP_LABEL = {"es": "{st} SENADO", "ja": "{name} 上院", "zh": "{name} 参议院"}


def desk(lang: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    nat = national_snapshot(lang, now)
    strip, ticker = [], []
    for st in FEATURED:
        s = state_snapshot(st, lang, now)
        rows = [{"short": c["short"], "party": c["party"], "pct": c["pct"]} for c in s["candidates"] if c.get("on_card")][:3] \
            if s["results_available"] else [{"short": c["short"], "party": c["party"], "pct": None} for c in s["cards"]][:3]
        strip.append({"state": st, "label": STRIP_LABEL[lang].format(st=st, name=s["state_name"]), "status": s["phase"],
                      "results_available": s["results_available"], "rows": rows,
                      "counted_vs_2022_pct": (s["counted_vs_2022"] or {}).get("pct"), "poll_close_last_et": s["poll_close"]["last_et"],
                      "call": s["call"]})
        ticker.append(_ticker_line(s, lang))
    upcoming = [x for x in nat["schedule"] if _t(x["et"]) > now]
    nxt = upcoming[0] if upcoming else None
    return {"as_of": now.isoformat(timespec="seconds"), "lang": lang, "national": nat, "strip": strip,
            "next_close": nxt, "ticker": [t for t in ticker if t]}


def fmt_et(iso: str, lang: str) -> str:
    t = _t(iso).astimezone(ET)
    h12 = t.hour % 12 or 12
    mm = f":{t.minute:02d}" if t.minute else ""
    if lang == "es":
        return f"{h12}{mm} {'p. m.' if t.hour >= 12 else 'a. m.'} (hora del Este)"
    if lang == "ja":
        jst = t.astimezone(timezone(timedelta(hours=9)))
        return f"米東部時間{'午後' if t.hour >= 12 else '午前'}{h12}時{(str(t.minute) + '分') if t.minute else ''}（日本時間{jst.day}日{jst.hour}時{(str(jst.minute) + '分') if jst.minute else ''}）"
    bj = t.astimezone(timezone(timedelta(hours=8)))
    return f"美东时间{'晚上' if t.hour >= 18 else ('下午' if t.hour >= 12 else '凌晨' if t.hour < 6 else '上午')}{h12}点{(str(t.minute) + '分') if t.minute else ''}（北京时间{bj.day}日{bj.hour}点{(str(bj.minute) + '分') if bj.minute else ''}）"


def _ticker_line(s: dict, lang: str) -> str:
    nm = s["state_name"]
    if s["call"]:
        return f"{nm}: {s['call']['text']}"
    if s["results_available"]:
        top = [c for c in s["candidates"] if c.get("on_card")][:2]
        bits = " · ".join(f"{c['short']} {c['pct']:.1f}%" for c in top)
        cnt = (s["counted_vs_2022"] or {}).get("pct")
        tail = {"es": f" · contados: {cnt:.0f}% del total de 2022", "ja": f" · 開票済み：2022年の総投票数の{cnt:.0f}%",
                "zh": f" · 已计票数为2022年总票数的{cnt:.0f}%"}[lang] if cnt is not None else ""
        lab = {"es": " (primeras preferencias)", "ja": "（第1希望）", "zh": "（第一选择）"}[lang] if s["rcv"] else ""
        return f"{nm}{lab}: {bits}{tail}"
    if s["phase"] == "preview":
        when = fmt_et(s["poll_close"]["last_et"], lang)
        return {"es": f"{nm}: las últimas urnas cierran a {'la' if when.startswith('1 ') else 'las'} {when}", "ja": f"{nm}：投票締め切り {when}",
                "zh": f"{nm}：投票将于{when}全部结束"}[lang]
    return {"es": f"{nm}: aún no hay conteo oficial publicado", "ja": f"{nm}：公式の開票結果はまだ発表されていません",
            "zh": f"{nm}：官方尚未公布计票结果"}[lang]

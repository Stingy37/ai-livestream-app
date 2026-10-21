"""Assemble desk.json, section by section, from the parsed agency products.

    doc, report = build_desk(prev_doc, storm_hint="CHAMPI")

Each section is built independently. If its source fails, the section keeps the value it had in
``prev_doc`` and is listed in ``doc["stale"]`` with the error in ``doc["provenance"][section]``.
Numbers (center, forecast, past track, agency table, ensemble, CPA) come only from the parsers in
sources.py; the text sections come from text.py, where every item is quote-checked.

Schema (schema_version 1) — what html/champi-desk.html reads:
    storm      {title, name, names, jtwc_id, jma_number}
    center     {lat, lon, timeUTC, source, stormRadiusKm, galeRadiusKm}
    forecast   {source, issuedUTC, points: [{timeUTC, lat, lon, radiusKm, cls, label}]}
    past       {source, points: [[timeUTC, lat, lon, wind_kmh]]}
    agencies   [{agency, sub, time, timeUTC, winds, gusts, pressure, moving, winds_kmh, gusts_kmh, pressure_hpa, lat, lon}]
    agencyNote str
    warnings   {stamp, items: [{cc, level, text, note, source_url, quote}]}
    headlines  [{main, sub, tag, source_url?, quote?}]
    ticker     [[tag, text]]
    impact     {PH|TW|JP: {name, local, agency, level, statusTag, status, signals|null, passes, chips, src}}
    ensemble   {runUTC, source, sets: [{key, name, color, mean_id, runUTC, members: [{id, pts: [[lat, lon]]}]}]}
    cpa        [{city, cc, lat, lon, km, timeUTC, track_lat, track_lon}]   (sorted by km)
    provenance {section: {source, url, fetched_at, ok, error?}}
    stale      [section, ...]
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from desk import geo, sources as S
from desk.text import Source, TextResult, country_text, dump_dropped, headline_text

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SECTIONS = ["storm", "center", "forecast", "past", "agencies", "agencyNote", "warnings", "headlines", "ticker",
            "impact", "ensemble", "cpa"]
REQUIRED = ("storm", "center", "forecast", "agencies")
COUNTRIES = {
    "PH": {"name": "Philippines", "agency": "PAGASA",
           "words": ["philippine", "luzon", "batanes", "pagasa", "rosal", "cagayan", "isabela", "bicol", "catanduanes", "samar"]},
    "TW": {"name": "Taiwan", "agency": "CWA",
           "words": ["taiwan", "taipei", "hualien", "yilan", "taitung", "cwa", "keelung", "kaohsiung"]},
    "JP": {"name": "Japan", "agency": "JMA",
           "words": ["okinawa", "ishigaki", "miyako", "yonaguni", "sakishima", "yaeyama", "japan", "jma", "naha"]},
}
TZ = {"JST": timezone(timedelta(hours=9)), "PHT": timezone(timedelta(hours=8)), "UTC+8": timezone(timedelta(hours=8)),
      "UTC": timezone.utc}
SAFETY = ["SAFETY", "Follow your local government's evacuation orders. This stream is not an official warning service."]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_local(iso_utc: str | None, zone: str) -> str:
    """'Oct 20, 9 AM JST' style (minutes shown only when not on the hour)."""
    if not iso_utc:
        return "time n/a"
    dt = S.parse_iso(iso_utc).astimezone(TZ[zone])
    if zone == "UTC":
        return f"{dt.strftime('%b')} {dt.day}, {dt:%H:%M} UTC"
    hour = dt.strftime("%I").lstrip("0") or "12"
    mins = f":{dt.minute:02d}" if dt.minute else ""
    return f"{dt.strftime('%b')} {dt.day}, {hour}{mins} {dt.strftime('%p')} {zone}"


def kmh(x: float | None) -> str:
    return f"{S.round5(x)} km/h" if x else "n/a"


# ─────────────────────────────────────────────────────────────────────────────
# raw source collection
# ─────────────────────────────────────────────────────────────────────────────

def collect(storm_hint: str, fallback_jma: str, fallback_jtwc: str) -> dict[str, Any]:
    """Fetch every source in parallel. Values are parsed dicts or Exception instances."""
    raw: dict[str, Any] = {}
    hint = (storm_hint or "").upper()

    # storm ids
    try:
        act = S.jtwc_active()
        pick = next((a for a in act if a["name"] == hint), act[0] if act else None)
        raw["jtwc_id"] = pick["id"] if pick else fallback_jtwc
        raw["jtwc_rss"] = pick
    except Exception as e:  # noqa: BLE001
        raw["jtwc_id"], raw["jtwc_rss"] = fallback_jtwc, e
    try:
        tcs = S.jma_active()
        raw["jma_tc"] = tcs[0]["tc"] if len(tcs) == 1 else None
        if raw["jma_tc"] is None and tcs:
            for tc in tcs:                 # several storms: the one whose name matches
                try:
                    st = S.jma_storm(tc["tc"])
                    if st["name_en"].upper() == hint:
                        raw["jma_tc"] = tc["tc"]
                        break
                except Exception:  # noqa: BLE001
                    continue
            raw["jma_tc"] = raw["jma_tc"] or tcs[0]["tc"]
        raw["jma_tc"] = raw["jma_tc"] or fallback_jma
    except Exception:  # noqa: BLE001
        raw["jma_tc"] = fallback_jma

    jid = raw["jtwc_id"]
    basin = {"wp": "WP", "sh": "SH", "io": "IO", "ep": "EP", "cp": "CP", "al": "AL"}.get(jid[:2], "WP")
    number = jid[2:4]
    jobs = {
        "jma": lambda: S.jma_storm(raw["jma_tc"]),
        "jtwc": lambda: S.jtwc_storm(jid),
        "pagasa": S.pagasa_bulletin,
        "cwa": lambda: S.cwa_storm(hint),
        "ensemble": lambda: S.ensemble(basin, number),
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futs = {k: pool.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                raw[k] = f.result()
            except Exception as e:  # noqa: BLE001
                log.warning("desk source %s failed: %s", k, e)
                raw[k] = e
    raw["fetched_at"] = now_iso()
    return raw


def ok(x) -> bool:
    return x is not None and not isinstance(x, Exception)


# ─────────────────────────────────────────────────────────────────────────────
# deterministic sections
# ─────────────────────────────────────────────────────────────────────────────

def sec_storm(raw) -> dict:
    jma, jtwc, pag, cwa = raw.get("jma"), raw.get("jtwc"), raw.get("pagasa"), raw.get("cwa")
    if not ok(jma) and not ok(jtwc):
        raise RuntimeError("neither JMA nor JTWC available")
    name = (jma["name_en"] if ok(jma) else jtwc["name"]).upper()
    title = (jtwc.get("title") if ok(jtwc) and jtwc.get("title") else (jma["analysis"]["label"] if ok(jma) else "TROPICAL CYCLONE")).upper()
    names = []
    if ok(pag) and pag.get("active") and pag.get("local_name"):
        names.append(f"Philippines: {pag['local_name']}")
    if ok(cwa) and cwa.get("active") and cwa.get("name_zh"):
        names.append(f"Taiwan: {cwa['name_zh']}")
    if ok(jma) and jma.get("number"):
        names.append(f"Japan: 台風{int(jma['number'][-2:])}号 {jma.get('name_jp', '')}".strip())
    return {"title": title, "name": name, "names": " · ".join(names),
            "jtwc_id": jtwc["number"] if ok(jtwc) else "", "jma_number": jma["number"] if ok(jma) else ""}


def sec_center(raw) -> dict:
    jma, jtwc = raw.get("jma"), raw.get("jtwc")
    if ok(jma):
        a = jma["analysis"]
        return {"lat": a["lat"], "lon": a["lon"], "timeUTC": a["timeUTC"], "source": "JMA analysis",
                "stormRadiusKm": a.get("stormRadiusKm"), "galeRadiusKm": a.get("galeRadiusKm")}
    if ok(jtwc):
        return {"lat": jtwc["lat"], "lon": jtwc["lon"], "timeUTC": jtwc["timeUTC"], "source": "JTWC warning",
                "stormRadiusKm": None, "galeRadiusKm": None}
    raise RuntimeError("no analysis position")


def sec_forecast(raw) -> dict:
    jma = raw.get("jma")
    if not ok(jma):
        raise RuntimeError(f"JMA unavailable: {raw.get('jma')}")
    pts = [{"timeUTC": f["timeUTC"], "lat": f["lat"], "lon": f["lon"], "radiusKm": f["radiusKm"], "cls": f["cls"],
            "label": f["label"], "wind_kmh": S.round5(f["wind_kmh"]), "pressure_hpa": f["pressure_hpa"]}
           for f in jma["forecasts"]]
    if not pts:
        raise RuntimeError("JMA has no forecast points")
    return {"source": f"JMA forecast issued {fmt_local(jma['issuedUTC'], 'JST')}", "issuedUTC": jma["issuedUTC"], "points": pts}


def sec_past(raw) -> dict:
    jtwc, jma = raw.get("jtwc"), raw.get("jma")
    if ok(jtwc) and jtwc.get("past"):
        pts = [[p["timeUTC"], p["lat"], round(p["lon"], 1), S.round5(S.kt_to_kmh(p["wind_kt"]))]
               for p in jtwc["past"] if p["wind_kt"] >= 25]
        return {"source": "JTWC 6-hourly positions (1-min winds)", "points": pts}
    if ok(jma) and jma.get("track"):
        return {"source": "JMA track (no times or winds published)", "points": [[None, la, lo, None] for la, lo in jma["track"]]}
    raise RuntimeError("no past track from JTWC or JMA")


def agency_rows(raw) -> list[dict]:
    rows = []
    jma, jtwc, pag, cwa = raw.get("jma"), raw.get("jtwc"), raw.get("pagasa"), raw.get("cwa")
    if ok(jma):
        a = jma["analysis"]
        rows.append({"agency": "JMA", "sub": "10-min", "time": fmt_local(a["timeUTC"], "JST"), "timeUTC": a["timeUTC"],
                     "winds": kmh(a["wind_kmh"]), "gusts": kmh(a["gust_kmh"]),
                     "pressure": f"{a['pressure_hpa']:.0f} hPa" if a["pressure_hpa"] else "n/a",
                     "moving": f"{a['course']} {a['speed_kmh']:.0f} km/h" if a.get("speed_kmh") else (a["course"] or "n/a"),
                     "winds_kmh": S.round5(a["wind_kmh"]), "gusts_kmh": S.round5(a["gust_kmh"]),
                     "pressure_hpa": a["pressure_hpa"], "lat": a["lat"], "lon": a["lon"], "url": jma["url"]})
    if ok(pag) and pag.get("active") and pag.get("wind_kmh"):
        rows.append({"agency": "PAGASA", "sub": "10-min", "time": fmt_local(pag.get("issuedUTC"), "PHT"),
                     "timeUTC": pag.get("issuedUTC"), "winds": kmh(pag["wind_kmh"]), "gusts": kmh(pag.get("gust_kmh")),
                     "pressure": "n/a", "moving": f"{pag.get('course', '')} {pag.get('speed_kmh', 0):.0f} km/h".strip(),
                     "winds_kmh": S.round5(pag["wind_kmh"]), "gusts_kmh": S.round5(pag.get("gust_kmh")), "pressure_hpa": None,
                     "lat": pag.get("lat"), "lon": pag.get("lon"), "url": pag["url"]})
    if ok(cwa) and cwa.get("active") and cwa.get("wind_ms"):
        rows.append({"agency": "CWA", "sub": "10-min", "time": fmt_local(cwa.get("timeUTC"), "UTC+8"),
                     "timeUTC": cwa.get("timeUTC"), "winds": kmh(cwa["wind_ms"] * 3.6),
                     "gusts": kmh(cwa["gust_ms"] * 3.6) if cwa.get("gust_ms") else "n/a",
                     "pressure": f"{cwa['pressure_hpa']:.0f} hPa" if cwa.get("pressure_hpa") else "n/a",
                     "moving": f"{cwa.get('course', '')} {cwa.get('speed_kmh', 0):.0f} km/h".strip(),
                     "winds_kmh": S.round5(cwa["wind_ms"] * 3.6), "gusts_kmh": S.round5((cwa.get("gust_ms") or 0) * 3.6) or None,
                     "pressure_hpa": cwa.get("pressure_hpa"), "lat": cwa.get("lat"), "lon": cwa.get("lon"), "url": cwa["url"]})
    if ok(jtwc) and jtwc.get("wind_kt"):
        mv = f"{S.deg_to_compass(jtwc['course_deg'])} {S.kt_to_kmh(jtwc['speed_kt']):.0f} km/h" if jtwc.get("course_deg") is not None else "n/a"
        rows.append({"agency": "JTWC", "sub": "1-min", "time": fmt_local(jtwc["timeUTC"], "UTC"), "timeUTC": jtwc["timeUTC"],
                     "winds": kmh(S.kt_to_kmh(jtwc["wind_kt"])), "gusts": kmh(S.kt_to_kmh(jtwc["gust_kt"])) if jtwc.get("gust_kt") else "n/a",
                     "pressure": "n/a", "moving": mv, "winds_kmh": S.round5(S.kt_to_kmh(jtwc["wind_kt"])),
                     "gusts_kmh": S.round5(S.kt_to_kmh(jtwc["gust_kt"])) if jtwc.get("gust_kt") else None, "pressure_hpa": None,
                     "lat": jtwc.get("lat"), "lon": jtwc.get("lon"), "url": jtwc["url"]})
    if not rows:
        raise RuntimeError("no agency reported numbers")
    return rows


def agency_note(rows: list[dict]) -> str:
    ten = [r["agency"] for r in rows if r["sub"] == "10-min"]
    one = [r["agency"] for r in rows if r["sub"] == "1-min"]
    parts = []
    if ten:
        parts.append(f"{', '.join(ten)}: 10-minute average winds")
    if one:
        parts.append(f"{', '.join(one)}: 1-minute winds, which read higher")
    return "; ".join(parts) + ". Numbers also differ by issue time and analysis."


def signal_summary(pag: dict) -> dict | None:
    if not (ok(pag) and pag.get("active")):
        return None
    raised = []
    for s in pag.get("signals") or []:
        full = "; ".join(f"{g}: {a}" for g, a in s["areas"].items())
        short = " · ".join(re.sub(r"\s*\([^)]*\)", "", a) for a in s["areas"].values())
        raised.append({"level": s["level"], "areas": short, "areas_full": full})
    return {"raised": raised, "max_raised": max((r["level"] for r in raised), default=0),
            "possible": pag.get("highest_possible") or [], "areas": raised[0]["areas"] if raised else "",
            "bulletin": pag.get("bulletin_no", ""), "issuedUTC": pag.get("issuedUTC")}


# ─────────────────────────────────────────────────────────────────────────────
# text sources for the LLM sections
# ─────────────────────────────────────────────────────────────────────────────

def latest_scraped_docs(run_root: Path, max_age_h: float = 12.0) -> list[dict]:
    files = sorted(run_root.glob("*/scenes/*/sources.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return []
    newest = files[0].parents[2]          # the run folder
    if datetime.now().timestamp() - files[0].stat().st_mtime > max_age_h * 3600:
        return []
    seen, docs = set(), []
    for f in newest.glob("scenes/*/sources.json"):
        try:
            for d in json.loads(f.read_text(encoding="utf-8")):
                if d.get("url") in seen or not d.get("main_text"):
                    continue
                seen.add(d["url"])
                docs.append(d)
        except (OSError, ValueError):
            continue
    return docs


AGENCY_HOSTS = ("jma.go.jp", "metoc.navy.mil", "cwa.gov.tw")


def agency_sources(raw) -> dict[str, Source]:
    from scraper.fetch import render_jma_typhoon_json

    out: dict[str, Source] = {}
    jma, jtwc, pag, cwa = raw.get("jma"), raw.get("jtwc"), raw.get("pagasa"), raw.get("cwa")
    if ok(pag) and pag.get("active") and pag.get("text"):
        out["PAGASA"] = Source("", "PAGASA", pag["url"], pag.get("issuedUTC") or "", pag["text"])
    if ok(cwa) and cwa.get("active") and cwa.get("text"):
        out["CWA"] = Source("", "CWA", cwa["url"], cwa.get("timeUTC") or "", cwa["text"])
    if ok(jma) and jma.get("_spec"):
        out["JMA"] = Source("", "JMA", jma["url"], jma["issuedUTC"], render_jma_typhoon_json(jma["_spec"])[0])
    if ok(jtwc):
        try:
            web = S.get_text(jtwc["url"])
        except Exception:  # noqa: BLE001
            web = ""
        if web:
            out["JTWC"] = Source("", "JTWC", jtwc["url"], jtwc["timeUTC"], web)
    return out


def scraped_for(docs: list[dict], words: list[str], n: int = 3) -> list[Source]:
    scored = []
    for d in docs:
        if any(h in d["url"] for h in AGENCY_HOSTS):
            continue
        low = d["main_text"].lower()
        hits = sum(low.count(w) for w in words)
        if hits >= 2:
            scored.append((hits, d))
    scored.sort(key=lambda x: -x[0])
    return [Source("", d.get("source_name") or "web", d["url"], d.get("published_at") or "", d["main_text"], kind="scraped")
            for _, d in scored[:n]]


def number_sources(srcs: list[Source]) -> list[Source]:
    for i, s in enumerate(srcs, 1):
        s.sid = f"S{i}"
    return srcs


# ─────────────────────────────────────────────────────────────────────────────
# the builder
# ─────────────────────────────────────────────────────────────────────────────

def build_desk(prev: dict | None, *, storm_hint: str = "", ask: Callable[[str, str], str] | None = None,
               run_root: Path | None = None, raw: dict | None = None, fallback_jma: str = "TC2636",
               fallback_jtwc: str = "wp2926") -> tuple[dict, dict]:
    prev = prev or {}
    raw = raw if raw is not None else collect(storm_hint, fallback_jma, fallback_jtwc)
    fetched = raw.get("fetched_at") or now_iso()
    doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "generated_at": now_iso()}
    prov: dict[str, dict] = {}
    stale: list[str] = []
    report: dict[str, Any] = {"dropped_text_items": [], "llm_calls": 0}

    def put(name: str, fn: Callable[[], Any], source: str, url: str = ""):
        try:
            val = fn()
            if val in (None, [], {}):
                raise RuntimeError("empty result")
            doc[name] = val
            prov[name] = {"source": source, "url": url, "fetched_at": fetched, "ok": True}
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:300]
            if name in prev:
                doc[name] = prev[name]
                stale.append(name)
                prov[name] = {"source": source, "url": url, "fetched_at": (prev.get("provenance", {}).get(name) or {}).get("fetched_at"),
                              "ok": False, "error": err, "kept_from": prev.get("generated_at")}
            else:
                prov[name] = {"source": source, "url": url, "fetched_at": fetched, "ok": False, "error": err}
            log.warning("desk section %s failed (%s)%s", name, err, "; kept the previous value" if name in prev else "")

    jma_url = raw["jma"]["url"] if ok(raw.get("jma")) else ""
    put("storm", lambda: sec_storm(raw), "JMA + JTWC + PAGASA + CWA", jma_url)
    put("center", lambda: sec_center(raw), "JMA analysis (JTWC fallback)", jma_url)
    put("forecast", lambda: sec_forecast(raw), "JMA forecast", jma_url)
    put("past", lambda: sec_past(raw), "JTWC .tcw past track", raw["jtwc"]["url"] if ok(raw.get("jtwc")) else "")
    put("agencies", lambda: agency_rows(raw), "JMA, PAGASA, CWA, JTWC")
    put("agencyNote", lambda: agency_note(doc.get("agencies") or []), "derived")

    def ens():
        e = raw.get("ensemble")
        if not ok(e):
            raise RuntimeError(str(e))
        parts = [f"{s['name']} {S.parse_iso(s['runUTC']).strftime('%HZ %b %d')}" for s in e["sets"]]
        return {"runUTC": e["runUTC"], "source": "NOAA NCEP ensemble tracker (" + ", ".join(parts) + ")",
                "sets": [{k: s[k] for k in ("key", "name", "color", "mean_id", "runUTC", "members")} for s in e["sets"]]}
    put("ensemble", ens, "NOAA NCEP ens_tracker (NOMADS)", S.NOMADS_ENS)

    def cpa():
        c, f = doc.get("center"), doc.get("forecast")
        if not c or not f:
            raise RuntimeError("no track")
        return geo.cpa_table([{"lat": c["lat"], "lon": c["lon"], "timeUTC": c["timeUTC"]}] + f["points"])
    put("cpa", cpa, "derived from the JMA forecast track")

    # ---- text sections --------------------------------------------------------------------
    pag = raw.get("pagasa")
    sig = signal_summary(pag)
    agencies_src = agency_sources(raw)
    docs = latest_scraped_docs(run_root) if run_root else []
    storm_label = f"{(doc.get('storm') or {}).get('title', 'Typhoon').title()} {(doc.get('storm') or {}).get('name', storm_hint).title()}"
    results: dict[str, TextResult] = {}
    if ask is not None:
        jobs = {}
        for cc, meta in COUNTRIES.items():
            srcs = ([agencies_src[meta["agency"]]] if meta["agency"] in agencies_src else []) + scraped_for(docs, meta["words"])
            srcs = number_sources([Source(s.sid, s.agency, s.url, s.issued, s.text, s.kind) for s in srcs])
            jobs[cc] = (lambda srcs=srcs, meta=meta: country_text(ask, storm_label, meta["name"], meta["agency"], srcs))
        head_srcs = number_sources([Source("", s.agency, s.url, s.issued, s.text, s.kind) for s in agencies_src.values()]
                                   + scraped_for(docs, sum((m["words"] for m in COUNTRIES.values()), []), n=3))
        jobs["headlines"] = lambda: headline_text(ask, storm_label, head_srcs)
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futs = {k: pool.submit(f) for k, f in jobs.items()}
            for k, f in futs.items():
                try:
                    results[k] = f.result()
                except Exception as e:  # noqa: BLE001
                    log.warning("desk text %s failed: %s", k, e)
        report["llm_calls"] = sum(r.calls for r in results.values())
        report["dropped_text_items"] = dump_dropped(list(results.values()))

    latest = max([s.issued for s in agencies_src.values() if s.issued] or [fetched])

    def warnings():
        items = []
        for cc, meta in COUNTRIES.items():
            r = results.get(cc)
            w = (r.items.get("warning") if r else None)
            lvl = (r.items.get("level") if r else "none") or "none"
            note = ""
            if cc == "PH" and sig and sig["raised"]:
                lvl = "hot"
                note = f"Wind Signal No. {sig['max_raised']} raised (PAGASA Bulletin #{sig['bulletin']})"
            if w:
                items.append({"cc": cc, "level": lvl, "text": f"<b>{meta['agency']}:</b> {_html(w['text'])}", "note": note,
                              "source_url": w["source_url"], "quote": w["quote"]})
            elif cc == "PH" and sig and sig["raised"]:
                items.append({"cc": cc, "level": lvl, "text": f"<b>PAGASA:</b> Wind Signal No. {sig['max_raised']} over {_html(sig['areas'])}.",
                              "note": "", "source_url": pag["url"], "quote": ""})
            else:
                src = agencies_src.get(meta["agency"])
                when = fmt_local(src.issued, "UTC+8") if src and src.issued else "this update"
                items.append({"cc": cc, "level": "none",
                              "text": f"<b>{meta['agency']}:</b> No warning text reported for {meta['name']} as of {when}.",
                              "note": note, "source_url": src.url if src else "", "quote": ""})
        return {"stamp": f"As of {fmt_local(latest, 'UTC+8')}", "items": items}

    def impact():
        out = {}
        cpa_rows = doc.get("cpa") or []
        passes = geo.passes_by_country(cpa_rows)
        st = doc.get("storm") or {}
        locals_ = {"PH": (pag.get("local_name") if ok(pag) else "") or "",
                   "TW": (raw["cwa"].get("name_zh") if ok(raw.get("cwa")) else "") or "",
                   "JP": f"台風{int(st['jma_number'][-2:])}号" if st.get("jma_number") else ""}
        for cc, meta in COUNTRIES.items():
            r = results.get(cc)
            lvl = (r.items.get("level") if r else "none") or "none"
            status = (r.items.get("status") or {}).get("text") if r and r.items.get("status") else ""
            col = {"name": meta["name"], "local": locals_[cc] or (((prev.get("impact") or {}).get(cc) or {}).get("local", "")),
                   "agency": meta["agency"], "passes": passes.get(cc, []), "signals": None,
                   "chips": [[c["icon"], c["label"], c["value"]] for c in ((r.items.get("chips") if r else None) or [])]}
            if cc == "PH" and sig is not None:
                col["signals"] = {"possible": sig["possible"], "raised": sig["raised"], "areas": sig["areas"]}
                if sig["raised"]:
                    lvl = "hot"
                    status = status or f"Wind Signal No. {sig['max_raised']} raised."
            col["level"] = lvl
            col["statusTag"] = (f"SIGNAL NO. {sig['max_raised']}" if cc == "PH" and sig and sig["raised"]
                                else {"hot": "WARNING", "watch": "WATCH"}.get(lvl, "MONITORING"))
            src = agencies_src.get(meta["agency"])
            col["status"] = status or f"No {meta['agency']} warning reported as of {fmt_local(src.issued, 'UTC+8') if src and src.issued else 'this update'}."
            used = sorted({c["agency"] for c in ((r.items.get("chips") if r else None) or [])}
                          | ({r.items["status"]["agency"]} if r and r.items.get("status") else set()))
            col["src"] = (f"{meta['agency']} " + (fmt_local(src.issued, "UTC+8") if src and src.issued else "")).strip()
            if used:
                col["src"] = ", ".join(used) + f" ({fmt_local(latest, 'UTC+8')})"
            out[cc] = col
        return out

    def headlines():
        rows = doc.get("agencies") or []
        j = rows[0] if rows else None
        hs = []
        if j and doc.get("center"):
            c = doc["center"]
            st = doc.get("storm") or {}
            hs.append({"main": f"{st.get('name', '').title()}: {j['winds']} winds, {j['pressure']}".replace(", n/a", ""),
                       "sub": f"{j['agency']}: center near {c['lat']:.1f}°N {c['lon']:.1f}°E, moving {j['moving']} ({j['time']})",
                       "tag": "LIVE TRACK"})
        r = results.get("headlines")
        hs += (r.items.get("headlines") if r else []) or []
        return hs[:5]

    def ticker():
        items = []
        rows = {r["agency"]: r for r in doc.get("agencies") or []}
        if "JMA" in rows and doc.get("center"):
            j, c = rows["JMA"], doc["center"]
            items.append(["JMA", f"Center near {c['lat']:.1f}°N {c['lon']:.1f}°E at {j['time']}: {j['winds']} winds, gusts {j['gusts']}, {j['pressure']}, moving {j['moving']}"])
        if "JTWC" in rows:
            items.append(["JTWC", f"1-minute sustained winds {rows['JTWC']['winds']}, gusts {rows['JTWC']['gusts']} ({rows['JTWC']['time']})"])
        if sig and sig["raised"]:
            for s in sig["raised"]:
                items.append(["PAGASA", f"Wind Signal No. {s['level']}: {s['areas']}"])
        if sig and sig["possible"]:
            items.append(["PAGASA", "Highest wind signal that may be raised: No. " + " or ".join(map(str, sig["possible"]))])
        if "CWA" in rows:
            items.append(["CWA", f"{rows['CWA']['winds']} winds, {rows['CWA']['pressure']} ({rows['CWA']['time']})"])
        for cc in COUNTRIES:
            r = results.get(cc)
            for t in ((r.items.get("ticker") if r else None) or []):
                items.append([t["agency"].upper()[:12], t["text"]])
        note = doc.get("agencyNote")
        if note:
            items.append(["WINDS", note])
        items.append(SAFETY)
        return items

    if ask is not None:
        put("warnings", warnings, "LLM over agency texts + scraped pages (quote-checked)")
        put("impact", impact, "LLM over agency texts + scraped pages (quote-checked) + PAGASA signals")
        put("headlines", headlines, "parsers + LLM (quote-checked)")
    put("ticker", ticker, "parsers + LLM (quote-checked)")
    for name in ("warnings", "impact", "headlines"):           # no LLM this run: keep the previous text
        if name not in doc and name in prev:
            doc[name] = prev[name]
            stale.append(name)
            prov[name] = {"source": "LLM", "ok": False, "error": "LLM disabled for this update", "kept_from": prev.get("generated_at")}

    doc["provenance"] = prov
    doc["stale"] = stale
    report["fresh"] = [s for s in SECTIONS if prov.get(s, {}).get("ok")]
    report["stale"] = stale
    report["missing"] = [s for s in SECTIONS if s not in doc]
    return doc, report


def _html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────────────────────────────────────
# validation
# ─────────────────────────────────────────────────────────────────────────────

def validate(doc: dict) -> list[str]:
    p: list[str] = []
    if doc.get("schema_version") != SCHEMA_VERSION:
        p.append("schema_version")
    for k in REQUIRED:
        if not doc.get(k):
            p.append(f"missing {k}")

    def ll(lat, lon, where):
        if not (isinstance(lat, (int, float)) and -60 <= lat <= 60 and isinstance(lon, (int, float)) and 80 <= lon <= 200):
            p.append(f"{where}: lat/lon out of range ({lat}, {lon})")

    def t(v, where):
        try:
            S.parse_iso(v)
        except Exception:  # noqa: BLE001
            p.append(f"{where}: bad time {v!r}")

    c = doc.get("center") or {}
    if c:
        ll(c.get("lat"), c.get("lon"), "center")
        t(c.get("timeUTC", ""), "center")
    pts = (doc.get("forecast") or {}).get("points") or []
    for i, f in enumerate(pts):
        ll(f.get("lat"), f.get("lon"), f"forecast[{i}]")
        t(f.get("timeUTC", ""), f"forecast[{i}]")
    times = [f.get("timeUTC") for f in pts]
    if times != sorted(times):
        p.append("forecast points not in time order")
    for i, pt in enumerate((doc.get("past") or {}).get("points") or []):
        ll(pt[1], pt[2], f"past[{i}]")
    for s in (doc.get("ensemble") or {}).get("sets") or []:
        for m in s.get("members") or []:
            for la, lo in m.get("pts") or []:
                if not (-60 <= la <= 60 and 80 <= lo <= 220):
                    p.append(f"ensemble {s.get('name')} {m.get('id')}: point out of range")
                    break
    for a in doc.get("agencies") or []:
        for k in ("agency", "sub", "time", "winds", "gusts", "pressure", "moving"):
            if k not in a:
                p.append(f"agency row missing {k}")
    return p

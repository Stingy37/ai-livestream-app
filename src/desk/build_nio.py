"""desk.json for the India streams (DESK_REGION=nio): IMD RSMC New Delhi first, JTWC as the labelled second source.

    doc, report = build_desk_nio(prev, storm_hint="ARNAB")

Sections: storm, center, forecast (IMD's table; JTWC's if IMD's bulletin is unreadable), past (JTWC), agencies
(IMD 3-min, JTWC 1-min), and "in" (docs/INDIA_DESK.md): IMD's bulletin as sentences and structured fields, IMD district
colour levels, closest passes along IMD's track. A section whose source fails keeps its previous value (listed in
"stale"), as in the Western Pacific builder. No LLM.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from desk import geo, sources as S, sources_nio as N

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SECTIONS_NIO = ["storm", "center", "forecast", "past", "agencies", "in"]
NIO_JTWC = ("io", "sh")                 # JTWC ids of North Indian Ocean (and Southern Hemisphere) storms
REQUIRED = ("storm", "center", "forecast", "agencies")
# closest passes along IMD's track (in.cpa)
PLACES = [("Visakhapatnam", 17.69, 83.22), ("Kakinada", 16.96, 82.24), ("Yanam", 16.73, 82.21), ("Rajahmundry", 17.00, 81.80),
          ("Machilipatnam", 16.19, 81.14), ("Vijayawada", 16.51, 80.65), ("Bapatla", 15.90, 80.47), ("Nellore", 14.44, 79.99),
          ("Chennai", 13.08, 80.27), ("Puducherry", 11.93, 79.83), ("Srikakulam", 18.30, 83.90), ("Gopalpur", 19.26, 84.91),
          ("Puri", 19.81, 85.83), ("Bhubaneswar", 20.30, 85.82)]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ok(x) -> bool:
    return x is not None and not isinstance(x, Exception)


def ist_text(iso_utc: str | None) -> str:
    if not iso_utc:
        return ""
    t = S.parse_iso(iso_utc).astimezone(N.IST)
    return f"{t:%b} {t.day}, {t:%H:%M} IST"


def collect_nio(storm_hint: str, fallback_jtwc: str) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    hint = (storm_hint or "").upper()
    try:
        act = N.jtwc_active_nio()
        pick = next((a for a in act if a["name"] == hint), act[0] if act else None)
        raw["jtwc_id"] = pick["id"] if pick else fallback_jtwc
    except Exception:  # noqa: BLE001
        raw["jtwc_id"] = fallback_jtwc
    if not str(raw["jtwc_id"]).startswith(NIO_JTWC):   # a Western Pacific id (e.g. run_livestream.sh's default) is never
        raw["jtwc_id"] = ""                             # this storm: no JTWC this cycle rather than another storm's track
    jobs: dict[str, Callable[[], Any]] = {"jtwc": lambda: N.jtwc_nio(raw["jtwc_id"]) if raw["jtwc_id"] else None, "imd": N.imd_bulletin,
                                          "districts": N.district_warnings}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futs = {k: pool.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                raw[k] = f.result()
            except Exception as e:  # noqa: BLE001
                log.warning("nio source %s failed: %s", k, e)
                raw[k] = e
    raw["fetched_at"] = now_iso()
    return raw


def _imd_clean(imd: dict) -> dict:
    """The bulletin as published in desk.json: private parse helpers folded in (pressure only when it is current)."""
    out = {k: v for k, v in imd.items() if not k.startswith("_")}
    rs, tc = imd.get("_rsmc") or {}, imd.get("_tcac") or {}
    land = dict(out.get("landfall") or {})
    if rs.get("landfall_timeUTC") and (not land.get("date") or rs["landfall_timeUTC"][:10] == land.get("date")):
        land["timeUTC"] = rs["landfall_timeUTC"]
        land["time_basis"] = "IMD RSMC advisory (" + S.parse_iso(rs["landfall_timeUTC"]).strftime("%H%M UTC") + ")"
    elif land.get("date") and land.get("part_of_day") in N._PART_OF_DAY_IST:
        h = N._PART_OF_DAY_IST[land["part_of_day"]]
        t = datetime.fromisoformat(land["date"]).replace(hour=h, tzinfo=N.IST)
        land["timeUTC"] = S.iso(t.astimezone(timezone.utc))
        land["time_basis"] = f"estimated from IMD's '{land['part_of_day']}' ({h:02d}00 IST)"
    if land:
        out["landfall"] = land
    # pressure: IMD's National Bulletin gives none; the RSMC / TCAC figure is used only when its own wind matches the
    # bulletin's current wind (an earlier advisory's 999 hPa beside 35 kt is not the storm of 90 km/h)
    wind = out.get("wind_kmh")
    mid = (sum(wind) / 2 if isinstance(wind, list) else wind) if wind else None
    for src, kt_key in ((rs, "pressure_wind_kt"), (tc, "wind_kt")):
        if src.get("pressure_hpa") and src.get(kt_key) and mid and abs(src[kt_key] * 1.852 - mid) <= 15:
            out["pressure_hpa"] = src["pressure_hpa"]
            break
    return out


def _districts_today(d: dict) -> tuple[dict, dict]:
    """(state -> district -> colour for today's IST date, the full 3-day table)."""
    today = datetime.now(N.IST).date().isoformat()
    k = d["days"].index(today) if today in d["days"] else 0
    flat = {st: {name: cells[k]["colour"] for name, cells in ds.items() if cells[k]["colour"]} for st, ds in d["states"].items()}
    return flat, d["states"]


def build_desk_nio(prev: dict | None, *, storm_hint: str = "", raw: dict | None = None, fallback_jtwc: str = "io0226") -> tuple[dict, dict]:
    prev = prev or {}
    raw = raw if raw is not None else collect_nio(storm_hint, fallback_jtwc)
    fetched = raw.get("fetched_at") or now_iso()
    doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(), "region": "nio"}
    prov: dict[str, dict] = {}
    stale: list[str] = []
    jt, imd_raw, dist = raw.get("jtwc"), raw.get("imd"), raw.get("districts")
    imd = _imd_clean(imd_raw) if ok(imd_raw) else None

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
                prov[name] = {"source": source, "url": url, "ok": False, "error": err, "kept_from": prev.get("generated_at")}
            else:
                prov[name] = {"source": source, "url": url, "fetched_at": fetched, "ok": False, "error": err}
            log.warning("nio desk section %s failed (%s)%s", name, err, "; kept the previous value" if name in prev else "")

    imd_url = (imd or {}).get("source_url", "")

    def storm():
        name = (jt.get("name") if ok(jt) else "") or (storm_hint or "").upper()
        if not name:
            raise RuntimeError("no storm name")
        cls = (imd or {}).get("class") or (jt.get("title", "").title() if ok(jt) else "")
        pron = ""
        if imd and "Pronunciation" in imd.get("subject", ""):
            import re
            m = re.search(r"Pronunciation\s*:\s*([A-Za-z]+)", imd["subject"])
            pron = m.group(1) if m else ""
        names = [f"IMD: {name.title()}" + (f" ({pron})" if pron else "")] + ([f"JTWC: {jt['number']}"] if ok(jt) else [])
        return {"title": cls.upper() or "CYCLONE", "name": name, "names": " · ".join(names),
                "jtwc_id": raw.get("jtwc_id"), "imd_class": (imd or {}).get("class"), "imd_class_short": (imd or {}).get("class_short")}
    put("storm", storm, "IMD National Bulletin + JTWC", imd_url)

    def center():
        if imd and imd.get("lat") is not None:
            return {"lat": imd["lat"], "lon": imd["lon"], "timeUTC": imd.get("observedUTC") or imd.get("issuedUTC"), "source": "IMD"}
        if ok(jt):
            return {"lat": jt["lat"], "lon": jt["lon"], "timeUTC": jt["timeUTC"], "source": "JTWC"}
        raise RuntimeError("no centre from IMD or JTWC")
    put("center", center, "IMD (JTWC fallback)", imd_url)

    def forecast():
        if imd and imd.get("forecast"):
            pts = [{"timeUTC": p["timeUTC"], "lat": p["lat"], "lon": p["lon"], "wind_kmh": p["wind_kmh"][1], "gust_kmh": p["gust_kmh"],
                    "label": p["class"], "class_short": p["class_short"]} for p in imd["forecast"]]
            return {"source": (imd.get("bulletin") or "IMD") + (f", {imd['issued_ist_text']}" if imd.get("issued_ist_text") else ""),
                    "issuedUTC": imd.get("issuedUTC"), "points": sorted(pts, key=lambda p: p["timeUTC"])}
        if ok(jt) and jt.get("forecasts"):
            return {"source": f"JTWC warning {jt['warning']} (1-min winds)", "issuedUTC": jt["timeUTC"],
                    "points": [{"timeUTC": f["timeUTC"], "lat": f["lat"], "lon": f["lon"], "wind_kmh": round(f["wind_kt"] * 1.852),
                                "label": "JTWC"} for f in jt["forecasts"]]}
        raise RuntimeError("no forecast track")
    put("forecast", forecast, "IMD forecast table (JTWC fallback)", imd_url)

    def past():
        if not ok(jt) or not jt.get("past"):
            raise RuntimeError(f"JTWC: {jt}")
        return {"source": "JTWC 6-hourly positions (1-min winds)", "points": [[p["timeUTC"], p["lat"], p["lon"], p["wind_kt"]] for p in jt["past"]]}
    put("past", past, "JTWC .tcw past track", f"{S.JTWC_PRODUCTS}/{raw.get('jtwc_id')}.tcw")

    def agencies():
        rows = []
        if imd and imd.get("wind_kmh"):
            w = imd["wind_kmh"]
            mv = imd.get("movement") or {}
            rows.append({"agency": "IMD", "sub": "3-min", "time": ist_text(imd.get("observedUTC") or imd.get("issuedUTC")),
                         "timeUTC": imd.get("observedUTC") or imd.get("issuedUTC"),
                         "winds": f"{w[0]}-{w[1]} km/h" if isinstance(w, list) else f"{w} km/h", "gusts": f"{imd['gust_kmh']} km/h",
                         "pressure": f"{imd['pressure_hpa']:.0f} hPa" if imd.get("pressure_hpa") else "n/a",
                         "moving": f"{mv.get('dir', '')} {mv.get('kmh', '')} km/h".strip() if mv.get("kmh") else "n/a",
                         "winds_kmh": w[1] if isinstance(w, list) else w, "gusts_kmh": imd["gust_kmh"], "class": imd.get("class"),
                         "lat": imd.get("lat"), "lon": imd.get("lon"), "url": imd_url})
        if ok(jt) and jt.get("wind_kt"):
            mv = f"{S.deg_to_compass(jt['course_deg'])} {round(jt['speed_kt'] * 1.852)} km/h" if jt.get("course_deg") is not None and jt.get("speed_kt") else "n/a"
            rows.append({"agency": "JTWC", "sub": "1-min", "time": jt["timeUTC"][8:10] + " " + S.parse_iso(jt["timeUTC"]).strftime("%b, %H:%M UTC"),
                         "timeUTC": jt["timeUTC"], "winds": f"{S.round5(S.kt_to_kmh(jt['wind_kt']))} km/h",
                         "gusts": f"{S.round5(S.kt_to_kmh(jt['gust_kt']))} km/h" if jt.get("gust_kt") else "n/a", "pressure": "n/a",
                         "moving": mv, "winds_kmh": S.round5(S.kt_to_kmh(jt["wind_kt"])), "wind_kt": jt["wind_kt"],
                         "lat": jt.get("lat"), "lon": jt.get("lon"), "url": jt["url"]})
        return rows
    put("agencies", agencies, "IMD (3-min), JTWC (1-min)")

    def india():
        prev_in = prev.get("in") or {}
        out: dict[str, Any] = {}
        if imd:
            out["imd"] = imd
        elif prev_in.get("imd"):
            out["imd"], out["imd_stale"] = prev_in["imd"], True
        if ok(dist):
            out["districts"], out["districts_days"] = _districts_today(dist)
            out["districts_issued"], out["districts_updated"] = dist["issued"], dist["updated_at"]
            out["districts_dates"] = dist["days"]
        elif prev_in.get("districts"):
            for k in ("districts", "districts_days", "districts_issued", "districts_updated", "districts_dates"):
                if k in prev_in:
                    out[k] = prev_in[k]
            out["districts_stale"] = True
        c, f = doc.get("center"), (doc.get("forecast") or {}).get("points") or []
        if c and f:
            track = [{"lat": c["lat"], "lon": c["lon"], "timeUTC": c["timeUTC"]}] + [p for p in f if p["timeUTC"] > c["timeUTC"]]
            rows = []
            for name, la, lo in PLACES:
                ca = geo.closest_approach(track, la, lo)
                if ca:
                    rows.append({"place": name, "lat": la, "lon": lo, "km": ca["km"], "timeUTC": ca["timeUTC"],
                                 "track_lat": ca["lat"], "track_lon": ca["lon"]})
            out["cpa"] = sorted(rows, key=lambda r: r["km"])
            out["cpa_basis"] = "closest point of " + ("IMD's forecast track" if (imd or {}).get("forecast") else "JTWC's forecast track")
        if ok(jt):
            out["jtwc"] = {"id": jt["id"], "number": jt["number"], "warning": jt["warning"], "timeUTC": jt["timeUTC"], "wind_kt": jt.get("wind_kt"),
                           "gust_kt": jt.get("gust_kt"), "peak_kt": max([p["wind_kt"] for p in jt.get("forecasts") or []] or [jt.get("wind_kt") or 0]),
                           "forecast": [{"timeUTC": p["timeUTC"], "lat": p["lat"], "lon": p["lon"], "wind_kt": p["wind_kt"]} for p in jt.get("forecasts") or []],
                           "url": jt["url"]}
        if not out.get("imd") and not out.get("districts"):
            raise RuntimeError(f"IMD bulletin: {imd_raw}; districts: {dist}")
        return out
    put("in", india, "IMD National Bulletin + RSMC advisory + IMD district warnings (WFS) + JTWC", imd_url)
    if doc.get("in", {}).get("imd"):     # the same Telugu / Tamil sentences the narration reads, for the page's ticker and lower third
        from desk.bulletin import build as say

        text = {}
        for lang in ("te", "ta"):
            for part in ("now", "landfall", "warnings"):
                try:
                    text.setdefault(lang, {})[part] = say(f"in_{lang}_{part}", doc).splitlines()
                except Exception as error:  # noqa: BLE001 - a part IMD did not state this bulletin
                    log.info("desk text in_%s_%s skipped: %s", lang, part, error)
        doc["in"]["text"] = text

    doc["provenance"] = prov
    doc["stale"] = stale
    report = {"fresh": [s for s in SECTIONS_NIO if prov.get(s, {}).get("ok")], "stale": stale,
              "missing": [s for s in SECTIONS_NIO if s not in doc], "llm_calls": 0, "dropped_text_items": []}
    return doc, report


def validate_nio(doc: dict) -> list[str]:
    p: list[str] = []
    if doc.get("schema_version") != SCHEMA_VERSION:
        p.append("schema_version")
    for k in REQUIRED:
        if not doc.get(k):
            p.append(f"missing {k}")

    def ll(lat, lon, where):
        if not (isinstance(lat, (int, float)) and -40 <= lat <= 40 and isinstance(lon, (int, float)) and 40 <= lon <= 110):
            p.append(f"{where}: lat/lon out of range ({lat}, {lon})")
    c = doc.get("center") or {}
    if c:
        ll(c.get("lat"), c.get("lon"), "center")
        # EC2's /api/v1/desk accepts centres at 80-200 E only (ec2/server.py): an Arabian Sea storm needs that widened
        if isinstance(c.get("lon"), (int, float)) and c["lon"] < 80:
            p.append("center west of 80E: EC2 would reject this desk (widen ec2/server.py's range first)")
    pts = (doc.get("forecast") or {}).get("points") or []
    for i, f in enumerate(pts):
        ll(f.get("lat"), f.get("lon"), f"forecast[{i}]")
        try:
            S.parse_iso(f.get("timeUTC", ""))
        except Exception:  # noqa: BLE001
            p.append(f"forecast[{i}]: bad time")
    if [f.get("timeUTC") for f in pts] != sorted(f.get("timeUTC") for f in pts):
        p.append("forecast points not in time order")
    for a in doc.get("agencies") or []:
        for k in ("agency", "sub", "time", "winds", "gusts", "pressure", "moving"):
            if k not in a:
                p.append(f"agency row missing {k}")
    return p


def fallback_jtwc_id() -> str:
    jid = os.environ.get("DESK_JTWC_ID", "")
    return jid if jid.startswith(NIO_JTWC) else "io0226"

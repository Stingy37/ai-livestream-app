"""Deterministic parsers for the agency products behind desk.json.

Every function returns plain dicts (numbers as numbers, times as ISO UTC strings) and raises on a
failure; build.py decides what to do with a failure. Nothing here calls an LLM.

    jma_active()                 JMA targetTc.json  -> [{"tc": "TC2636", "number": "2630", ...}]
    jma_storm(tc)                specifications.json + forecast.json -> analysis, forecasts, track
    jtwc_active()                JTWC RSS -> [{"id": "wp2926", "number": "29W", "name": "CHAMPI", "title": ...}]
    jtwc_storm(id)               <id>.tcw (forecast + 6-hourly past track) + <id>web.txt (warning text)
    pagasa_bulletin()            PAGASA severe weather bulletin page -> {"active": bool, ...}
    cwa_storm(name)              CWA TY_NEWS-Data.js (public, no API key) -> current CWA analysis
    ensemble(basin, number)      NCEP ens_tracker on NOMADS -> GEFS + FNMOC member tracks
"""

from __future__ import annotations

import html as htmllib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from desk.http import FetchError, get_json, get_text

log = logging.getLogger(__name__)

JMA_BASE = "https://www.jma.go.jp/bosai/typhoon/data"
JTWC_RSS = "https://www.metoc.navy.mil/jtwc/rss/jtwc.rss"
JTWC_PRODUCTS = "https://www.metoc.navy.mil/jtwc/products"
PAGASA_BULLETIN = "https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin"
CWA_TY_NEWS = "https://www.cwa.gov.tw/Data/js/typhoon/TY_NEWS-Data.js"
NOMADS_ENS = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/ens_tracker/prod"

COMPASS_JP = {"北": "N", "北北東": "NNE", "北東": "NE", "東北東": "ENE", "東": "E", "東南東": "ESE", "南東": "SE",
              "南南東": "SSE", "南": "S", "南南西": "SSW", "南西": "SW", "西南西": "WSW", "西": "W", "西北西": "WNW",
              "北西": "NW", "北北西": "NNW", "ほとんど停滞": "Almost stationary", "停滞": "Stationary"}
COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
JMA_INTENSITY = {"猛烈な": ("vi", "Violent"), "非常に強い": ("vs", "Very strong"), "強い": ("ty", "Strong")}
JMA_CATEGORY = {"TY": ("ty", "Typhoon"), "STS": ("ts", "Severe trop. storm"), "TS": ("ts", "Tropical storm"),
                "TD": ("ts", "Tropical depression"), "LOW": ("ts", "Low")}


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def kt_to_kmh(kt: float) -> float:
    return kt * 1.852


def round5(x: float | None) -> int | None:
    return None if x is None else int(5 * round(x / 5))


def deg_to_compass(deg: float) -> str:
    return COMPASS_16[int((deg % 360) / 22.5 + 0.5) % 16]


_WORD_DIR = {"north": "N", "south": "S", "east": "E", "west": "W", "northeast": "NE", "northwest": "NW",
             "southeast": "SE", "southwest": "SW"}


def words_to_compass(words: str) -> str:
    """'West Northwestward' -> 'WNW'; 'Northward' -> 'N'; unknown words are kept as written."""
    parts = [w.lower().removesuffix("ward").removesuffix("wards") for w in words.replace("-", " ").split()]
    if parts and all(w in _WORD_DIR for w in parts):
        return "".join(_WORD_DIR[w] for w in parts)
    return words.strip()


def wind_cls(kmh: float | None) -> str:
    """The page's windCls thresholds (km/h)."""
    if kmh is None:
        return "ty"
    return "vi" if kmh >= 240 else "vs" if kmh >= 185 else "ty" if kmh >= 118 else "ts"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _ll(tok: str) -> float:
    """'159N' / '1356E' (tenths of a degree, ATCF style) -> signed degrees."""
    m = re.fullmatch(r"(\d+)([NSEW])", tok.strip())
    if not m:
        raise ValueError(f"bad ATCF coordinate {tok!r}")
    v = int(m.group(1)) / 10.0
    if m.group(2) in "SW":
        v = -v
    if m.group(2) == "W":
        v = 360.0 + v      # keep the western Pacific contiguous
    return v


# ─────────────────────────────────────────────────────────────────────────────
# JMA
# ─────────────────────────────────────────────────────────────────────────────

def jma_active() -> list[dict]:
    data = get_json(f"{JMA_BASE}/targetTc.json")
    return [{"tc": d["tropicalCyclone"], "number": d.get("typhoonNumber") or "", "category": d.get("category", ""),
             "issue": d.get("issue")} for d in data if d.get("tropicalCyclone")]


def _part_name(p) -> str:
    return p["part"] if isinstance(p.get("part"), str) else (p.get("part") or {}).get("en", "")


def parse_jma(spec: list, fcst: list | None, tc: str) -> dict:
    title = next(p for p in spec if _part_name(p) == "title")
    analysis = next(p for p in spec if _part_name(p) == "Analysis")
    out = {"tc": tc, "number": title.get("typhoonNumber", ""), "name_en": (title.get("name") or {}).get("en", ""),
           "name_jp": (title.get("name") or {}).get("jp", ""), "issuedUTC": iso(parse_iso(title["issue"]["UTC"])),
           "url": f"{JMA_BASE}/{tc}/specifications.json"}

    def point(p: dict) -> dict:
        lat, lon = p["position"]["deg"]
        mw = (p.get("maximumWind") or {})
        sus = (mw.get("sustained") or {})
        gust = (mw.get("gust") or {})
        sus_kt = float(sus["kt"]) if sus.get("kt") not in (None, "", "-") else None
        gust_kt = float(gust["kt"]) if gust.get("kt") not in (None, "", "-") else None
        cat = ((p.get("category") or {}).get("en") or "").upper()
        intensity = p.get("intensity") or ""
        cls, label = JMA_INTENSITY.get(intensity) or JMA_CATEGORY.get(cat) or (wind_cls(kt_to_kmh(sus_kt) if sus_kt else None), cat or "Tropical cyclone")
        speed = p.get("speed") or {}
        course = p.get("course") or ""
        return {"timeUTC": iso(parse_iso(p["validtime"]["UTC"])), "lat": float(lat), "lon": float(lon),
                "hours": int(p.get("advancedHours", 0)), "category": cat, "intensity_jp": intensity,
                "cls": cls, "label": label, "wind_kt": sus_kt, "gust_kt": gust_kt,
                "wind_kmh": kt_to_kmh(sus_kt) if sus_kt else None, "gust_kmh": kt_to_kmh(gust_kt) if gust_kt else None,
                "pressure_hpa": float(p["pressure"]) if str(p.get("pressure", "")).replace(".", "").isdigit() else None,
                "course": COMPASS_JP.get(course, course), "speed_kmh": float(speed["km/h"]) if str(speed.get("km/h", "")).isdigit() else None,
                "radiusKm": (p.get("probabilityCircleRadius") or {}).get("km")}

    a = point(analysis)
    storm = [w for w in (analysis.get("stormWarning") or []) if (w.get("range") or {}).get("km")]
    gale = [w for w in (analysis.get("galeWarning") or []) if (w.get("range") or {}).get("km")]
    a["stormRadiusKm"] = max((w["range"]["km"] for w in storm), default=None)
    a["galeRadiusKm"] = max((w["range"]["km"] for w in gale), default=None)
    out["analysis"] = a
    out["forecasts"] = [point(p) for p in spec if _part_name(p).startswith("Forecast")]
    # past track (no times in JMA's file): analysis part of forecast.json
    out["track"] = []
    for p in fcst or []:
        if _part_name(p) == "Analysis" and isinstance(p.get("track"), dict):
            out["track"] = [[float(la), float(lo)] for la, lo in (p["track"].get("typhoon") or [])]
    return out


def jma_storm(tc: str) -> dict:
    spec = get_json(f"{JMA_BASE}/{tc}/specifications.json")
    try:
        fcst = get_json(f"{JMA_BASE}/{tc}/forecast.json")
    except FetchError:
        fcst = None
    out = parse_jma(spec, fcst, tc)
    out["_spec"] = spec          # raw document, rendered to text for the text sections
    return out


# ─────────────────────────────────────────────────────────────────────────────
# JTWC
# ─────────────────────────────────────────────────────────────────────────────

def parse_jtwc_rss(xml: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<b>\s*([A-Za-z ]+?)\s+(\d{2}[A-Z])\s*\(([^)]+)\)\s*Warning\s*#\s*(\d+)", xml):
        title, number, name, warn = m.group(1).strip(), m.group(2), m.group(3).strip(), int(m.group(4))
        tail = xml[m.end(): m.end() + 3000]
        link = re.search(rf"{JTWC_PRODUCTS}/([a-z]{{2}}\d{{4}})web\.txt", tail)
        if link:
            out.append({"id": link.group(1), "number": number, "name": name.upper(), "title": " ".join(title.upper().split()),
                        "warning": warn})
    return out


def jtwc_active() -> list[dict]:
    return parse_jtwc_rss(get_text(JTWC_RSS))


def parse_jtwc(tcw: str, web: str, jtwc_id: str) -> dict:
    """Header + forecast points + 6-hourly past track from the .tcw file; winds/movement from the warning text."""
    lines = tcw.splitlines()
    head = next(l for l in lines if re.match(r"^\d{10}\s+\d{2}[A-Z]\s", l))
    hm = re.match(r"^(\d{10})\s+(\d{2}[A-Z])\s+(\S+)\s+(\d+)", head)
    t0 = datetime.strptime(hm.group(1), "%Y%m%d%H").replace(tzinfo=timezone.utc)
    out = {"id": jtwc_id, "number": hm.group(2), "name": hm.group(3), "warning": int(hm.group(4)),
           "timeUTC": iso(t0), "url": f"{JTWC_PRODUCTS}/{jtwc_id}web.txt"}
    fc = []
    for l in lines:
        m = re.match(r"^T(\d{3})\s+(\d+[NS])\s+(\d+[EW])\s+(\d+)", l)
        if m:
            fc.append({"hours": int(m.group(1)), "timeUTC": iso(t0 + timedelta(hours=int(m.group(1)))),
                       "lat": _ll(m.group(2)), "lon": _ll(m.group(3)), "wind_kt": float(m.group(4))})
    out["forecasts"] = fc
    past, seen = [], set()
    for l in lines:
        # "2926101700 123N1486E  90": storm number, 2-digit year, MMDDHH, position, 1-min wind (kt)
        m = re.match(r"^\d{2}(\d{8})\s+(\d+[NS])(\d+[EW])\s+(\d+)\s*$", l.strip())
        if m:
            when = datetime.strptime(m.group(1), "%y%m%d%H").replace(tzinfo=timezone.utc)
            if when in seen:
                continue
            seen.add(when)
            past.append({"timeUTC": iso(when), "lat": _ll(m.group(2)), "lon": _ll(m.group(3)), "wind_kt": float(m.group(4))})
    out["past"] = sorted(past, key=lambda p: p["timeUTC"])
    # warning text: present winds, movement
    w = re.search(r"MAX SUSTAINED WINDS - (\d+) KT, GUSTS (\d+) KT", web)
    mv = re.search(r"MOVEMENT PAST SIX HOURS - (\d+) DEGREES AT (\d+) KTS", web)
    pos = re.search(r"WARNING POSITION:\s*\n\s*(\d{6})Z --- NEAR (\d+\.\d)([NS]) (\d+\.\d)([EW])", web)
    out["wind_kt"] = float(w.group(1)) if w else (fc[0]["wind_kt"] if fc else None)
    out["gust_kt"] = float(w.group(2)) if w else None
    out["course_deg"] = float(mv.group(1)) if mv else None
    out["speed_kt"] = float(mv.group(2)) if mv else None
    if pos:
        out["lat"] = float(pos.group(2)) * (1 if pos.group(3) == "N" else -1)
        out["lon"] = float(pos.group(4)) * (1 if pos.group(5) == "E" else -1)
    elif fc:
        out["lat"], out["lon"] = fc[0]["lat"], fc[0]["lon"]
    title = re.search(r"SUBJ:\s*(.+?)\s+\d{2}[A-Z]\s*\(", web) or re.search(r"1\.\s*(.+?)\s+\d{2}[A-Z]\s*\(", web)
    out["title"] = " ".join(title.group(1).split()) if title else ""
    return out


def jtwc_storm(jtwc_id: str) -> dict:
    tcw = get_text(f"{JTWC_PRODUCTS}/{jtwc_id}.tcw")
    try:
        web = get_text(f"{JTWC_PRODUCTS}/{jtwc_id}web.txt")
    except FetchError:
        web = tcw
    return parse_jtwc(tcw, web, jtwc_id)


# ─────────────────────────────────────────────────────────────────────────────
# PAGASA
# ─────────────────────────────────────────────────────────────────────────────

_PHT = timezone(timedelta(hours=8))


def _visible_lines(el) -> list[str]:
    return [" ".join(t.split()) for t in el.itertext() if t and t.strip()]


def parse_pagasa(html: str) -> dict:
    """The current bulletin, or {"active": False} when PAGASA has none (storm outside PAR, no advisory)."""
    import lxml.html

    doc = lxml.html.fromstring(html)
    for bad in doc.xpath("//script|//style|//noscript"):
        bad.drop_tree()
    head = doc.xpath("//div[@id='swb'] | //*[contains(@class,'article-header')][contains(., 'Bulletin #')]")
    if not head:
        return {"active": False, "url": PAGASA_BULLETIN, "text": ""}
    box = head[0]
    while box is not None and len(box.text_content()) < 2000:
        box = box.getparent()
    lines = _visible_lines(box if box is not None else doc)
    text = "\n".join(lines)
    out = {"active": True, "url": PAGASA_BULLETIN, "text": text}
    m = re.search(r"Tropical Cyclone Bulletin #\s*(\w+)", text)
    out["bulletin_no"] = m.group(1) if m else ""
    m = re.search(r"(Super Typhoon|Typhoon|Severe Tropical Storm|Tropical Storm|Tropical Depression)\s+[\"“]([A-Za-z]+)[\"”]", text)
    out["category"], out["local_name"] = (m.group(1), m.group(2).capitalize()) if m else ("", "")
    m = re.search(r"Issued at (\d{1,2}):(\d{2})\s*([ap]m),\s*(\d{1,2}) (\w+) (\d{4})", text, re.I)
    if m:
        hh = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
        dt = datetime.strptime(f"{m.group(4)} {m.group(5)} {m.group(6)} {hh}:{m.group(2)}", "%d %B %Y %H:%M").replace(tzinfo=_PHT)
        out["issuedUTC"] = iso(dt)
    m = re.search(r"\((\d+\.\d+)\s*°?\s*N,\s*(\d+\.\d+)\s*°?\s*E\s*\)", text)
    if m:
        out["lat"], out["lon"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"Maximum sustained winds of (\d+) km/h near the center and gustiness of up to (\d+) km/h", text)
    if m:
        out["wind_kmh"], out["gust_kmh"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"Moving ([A-Za-z ]+?) at (\d+) km/h", text)
    if m:
        out["course"] = words_to_compass(m.group(1))
        out["speed_kmh"] = float(m.group(2))
    m = re.search(r"(?:center of the eye|center) was estimated based on all available data\s+(.+?)\s*\(", text)
    out["location"] = m.group(1).strip() if m else ""
    m = re.search(r"highest Wind Signal that may be raised during the passage of \w+ is Wind Signal No\. (\d)(?: or (\d))?", text)
    out["highest_possible"] = [int(x) for x in (m.groups() if m else ()) if x]
    out["signals"] = []
    for th in doc.xpath("//th[starts-with(@class,'signalno')]"):
        lvl = int(re.sub(r"\D", "", th.get("class")) or 0)
        tbody = th.getparent().getparent().getnext()
        areas = {}
        if tbody is not None:
            for li in tbody.xpath(".//ul/li[strong]"):
                group = " ".join(li.xpath("./strong")[0].text_content().split())
                vals = [" ".join(x.text_content().split()) for x in li.xpath("./ul/li")]
                vals = [v for v in vals if v and v != "-"]
                if vals:
                    areas[group] = "; ".join(vals)
        if lvl and areas:
            out["signals"].append({"level": lvl, "areas": areas})
    out["signals"].sort(key=lambda s: -s["level"])
    return out


def pagasa_bulletin() -> dict:
    return parse_pagasa(get_text(PAGASA_BULLETIN))


# ─────────────────────────────────────────────────────────────────────────────
# CWA (Taiwan)
# ─────────────────────────────────────────────────────────────────────────────

def parse_cwa(js: str, name: str | None = None) -> dict:
    """CWA's public typhoon data script (no API key). English block for numbers, Chinese for the local name."""
    m = re.search(r"var TYPHOON = \{(.*?)\};", js, re.S)
    names = re.findall(r"'([A-Z0-9-]+)':\{'Name':\{'C':'([^']*)','E':'([^']*)'\}", m.group(1) if m else "")
    if not names:
        return {"active": False, "url": CWA_TY_NEWS}
    pick = next((n for n in names if name and n[2].upper() == name.upper()), names[0])
    block = re.search(r"TY_LIST_1\['E'\] = (.*?);\s*\n", js, re.S)
    raw = "".join(re.findall(r"'((?:[^'\\]|\\.)*)'", block.group(1))) if block else ""
    # the English block can hold several storms; cut out the one with this id
    i = raw.find(f'id="{pick[0]}"')
    seg = raw[i:] if i >= 0 else raw
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", seg))
    text = " ".join(text.split())
    out = {"active": True, "url": CWA_TY_NEWS, "id": pick[0], "name_zh": pick[1], "name_en": pick[2], "text": text}
    cat = re.search(r'<span class="fa-red">([^<]+)</span>', seg)
    out["category"] = cat.group(1).strip().title() if cat else ""
    m = re.search(r"Position (\d{2})(\d{2})(\d{2})Z at (\d+\.\d)([NS]) (\d+\.\d)([EW])", text)
    tm = re.search(r"var TY_TIME = \{[^}]*'E':'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}) UTC'", js)
    if tm:
        out["timeUTC"] = iso(datetime(*map(int, tm.groups()), tzinfo=timezone.utc))
    if m:
        out["lat"] = float(m.group(4)) * (1 if m.group(5) == "N" else -1)
        out["lon"] = float(m.group(6)) * (1 if m.group(7) == "E" else -1)
    m = re.search(r"Movement:\s*([A-Z]+)\s+(\d+)\s*km/h", text)
    if m:
        out["course"], out["speed_kmh"] = m.group(1), float(m.group(2))
    m = re.search(r"Minimum pressure (\d+) hPa", text)
    out["pressure_hpa"] = float(m.group(1)) if m else None
    m = re.search(r"Max sustained winds near center (\d+) meter per second", text)
    out["wind_ms"] = float(m.group(1)) if m else None
    m = re.search(r"Gusts (\d+) meter per second", text)
    out["gust_ms"] = float(m.group(1)) if m else None
    return out


def cwa_storm(name: str | None = None) -> dict:
    return parse_cwa(get_text(CWA_TY_NEWS), name)


# ─────────────────────────────────────────────────────────────────────────────
# Ensemble (NCEP ens_tracker on NOMADS)
# ─────────────────────────────────────────────────────────────────────────────

ENSEMBLES = [
    {"key": "g", "name": "GEFS", "color": "#ff9a1f", "dir": "gefs", "mean_id": "aemn",
     "members": ["ac00"] + [f"ap{i:02d}" for i in range(1, 31)]},
    {"key": "n", "name": "Navy", "color": "#3fc3ff", "dir": "fens", "mean_id": "nemn",
     "members": ["nc00"] + [f"np{i:02d}" for i in range(1, 21)]},
]


def parse_atcf(text: str, basin: str, number: str, step_h: int = 12, max_h: int = 168) -> list[list[float]]:
    """[[lat, lon], ...] every ``step_h`` hours for one storm from an ATCF a-deck style file."""
    pts: dict[int, list[float]] = {}
    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) < 8 or f[0] != basin or f[1].lstrip("0") != number.lstrip("0"):
            continue
        h = int(f[5])
        if h % step_h or h > max_h or h in pts:
            continue
        lat, lon = _ll(f[6]), _ll(f[7])
        if lat == 0 and lon == 0:
            continue
        pts[h] = [lat, round(lon, 1)]
    return [pts[h] for h in sorted(pts)]


def _listing(url: str) -> list[str]:
    return re.findall(r'href="([^"/?][^"]*)"', get_text(url, ttl=300))


def ensemble(basin: str, number: str, now: datetime | None = None) -> dict:
    """Latest run of each ensemble that tracks this storm (newest cycle whose mean file contains it)."""
    now = now or datetime.now(timezone.utc)
    sets, runs, errors = [], [], []
    for spec in ENSEMBLES:
        found = None
        for days in (0, 1, 2):
            day = (now - timedelta(days=days)).strftime("%Y%m%d")
            try:
                cycles = sorted({c.strip("/") for c in _listing(f"{NOMADS_ENS}/{spec['dir']}.{day}/") if c.strip("/").isdigit()},
                                reverse=True)
            except FetchError:
                continue
            for cyc in cycles:
                base = f"{NOMADS_ENS}/{spec['dir']}.{day}/{cyc}/tctrack"
                try:
                    mean_pts = parse_atcf(get_text(f"{base}/{spec['mean_id']}.t{cyc}z.cyclone.trackatcfunix", ttl=600), basin, number)
                except FetchError:
                    continue
                if len(mean_pts) >= 2:
                    found = (day, cyc, base, mean_pts)
                    break
            if found:
                break
        if not found:
            errors.append(f"{spec['name']}: no run tracks {basin}{number}")
            continue
        day, cyc, base, mean_pts = found

        def member(mid: str, base=base, cyc=cyc):
            try:
                return mid, parse_atcf(get_text(f"{base}/{mid}.t{cyc}z.cyclone.trackatcfunix", ttl=600), basin, number)
            except FetchError:
                return mid, []

        with ThreadPoolExecutor(max_workers=8) as pool:
            members = [{"id": mid, "pts": pts} for mid, pts in pool.map(member, spec["members"]) if len(pts) >= 2]
        members.append({"id": spec["mean_id"], "pts": mean_pts})
        run = datetime.strptime(day + cyc, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        runs.append(run)
        sets.append({"key": spec["key"], "name": spec["name"], "color": spec["color"], "mean_id": spec["mean_id"],
                     "runUTC": iso(run), "url": base, "members": members})
    if not sets:
        raise FetchError("; ".join(errors) or "no ensemble data")
    return {"runUTC": iso(max(runs)), "sets": sets, "errors": errors}

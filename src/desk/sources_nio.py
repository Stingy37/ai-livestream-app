"""North Indian Ocean sources for the India desk (DESK_REGION=nio): IMD RSMC New Delhi + JTWC. No LLM.

    rsmc_links(html)            RSMC home page -> {"national", "rsmc", "tcac", "rain", "track_png", "subject"} URLs / text
    parse_national(text)        IMD National Bulletin (PDF text) -> class, position, movement, landfall, forecast table,
                                rain / wind / sea / surge / fishermen warnings, as IMD's sentences AND structured fields
    parse_rsmc(text)            RSMC Tropical Cyclone Advisory -> landfall time in UTC, analysis time, pressure (+ its wind)
    parse_districts(geojson)    IMD district warnings (GeoServer WFS, no geometry) -> {state: {district: colour}} for 3 days
    jtwc_nio(jtwc_id)           JTWC io####: parse_jtwc + the IO past track (positions written "118N 887E")
    imd_bulletin()              all of the above, fetched (PDFs read with desk.pdftext)

Every value is IMD's own (or JTWC's, labelled); nothing is estimated except where a field says so (landfall
timeUTC falls back to IMD's part of day -> a clock time, marked time_basis).
"""

from __future__ import annotations

import hashlib
import html as htmllib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from desk import sources as S
from desk.http import CACHE_DIR, _session, get_text
from desk.pdftext import pdf_text

log = logging.getLogger(__name__)

RSMC = "https://rsmcnewdelhi.imd.gov.in/"
DISTRICT_WFS = ("https://reactjs.imd.gov.in/geoserver/ows?service=WFS&version=1.1.0&request=GetFeature"
                "&typename=imd:district_warnings_india&srsname=EPSG:4326&outputFormat=application/json"
                "&propertyName=District,Date,UTC,Day_1,Day_2,Day_3,Day1_Color,Day2_Color,Day3_Color,Day1_text,Day2_text,"
                "Day3_text,updated_at&bbox=76,8,92,23,EPSG:4326")
IST = timezone(timedelta(hours=5, minutes=30))
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# IMD's scale (Depression .. Super Cyclonic Storm)
CLASS_SHORT = {"depression": "D", "deep depression": "DD", "cyclonic storm": "CS", "severe cyclonic storm": "SCS",
               "very severe cyclonic storm": "VSCS", "extremely severe cyclonic storm": "ESCS", "super cyclonic storm": "SuCS",
               "well marked low pressure area": "WML", "well-marked low pressure area": "WML", "low pressure area": "LPA"}
_CLASS_RX = r"(super cyclonic storm|extremely severe cyclonic storm|very severe cyclonic storm|severe cyclonic storm|cyclonic storm|deep depression|depression)"
# IMD district warning colours (Day*_Color) and hazard codes (Day_*)
DISTRICT_COLOUR = {1: "red", 2: "orange", 3: "yellow", 4: "green"}
DISTRICT_HAZARD = {"1": "No warning", "2": "Heavy rain", "3": "Heavy snow", "4": "Thunderstorm & lightning", "5": "Hailstorm",
                   "6": "Dust storm", "7": "Dust raising winds", "8": "Strong surface winds", "9": "Heat wave", "10": "Hot day",
                   "11": "Warm night", "12": "Cold wave", "13": "Cold day", "14": "Ground frost", "15": "Fog",
                   "16": "Very heavy rain", "17": "Extremely heavy rain"}
# IMD's district names (as its WFS layer spells them) by state; the layer has no state field
STATE_DISTRICTS = {
    "Andhra Pradesh": ["SRIKAKULAM", "VIZIANAGARAM", "PARVATHIPURAMMANYAM", "ALLURI SITHARAMA RAJU", "VISHAKHAPATNAM", "ANAKAPALLI",
                       "KAKINADA", "EAST GODAVARI", "KONASEEMA", "ELURU", "WEST GODAVARI", "NTR", "KRISHNA", "PALNADU", "GUNTUR",
                       "BAPATLA", "PRAKASAM", "SPSR NELLORE", "KURNOOL", "NANDYAL", "ANANTAPURAMU", "SRISATHYASAI", "YSR KADAPA",
                       "ANNAMAYYA", "CHITTOOR", "TIRUPATHI"],
    "Tamil Nadu": ["ARIYALUR", "CHENGALPATTU", "CHENNAI", "COIMBATORE", "CUDDALORE", "DHARMAPURI", "DINDIGUL", "ERODE", "KALLAKKURICHI",
                   "KANCHEEPURAM", "KANYAKUMARI", "KARUR", "KRISHNAGIRI", "MADURAI", "MAYILADUTHURAI", "NAGAPATTINAM", "NAMAKKAL",
                   "NILGIRIS", "PERAMBALUR", "PUDUKKOTTAI", "RAMANATHAPURAM", "RANIPPETTAI", "SALEM", "SIVAGANGAI", "TENKASI",
                   "THANJAVUR", "THENI", "THIRUCHIRAPALLI", "THIRUNELVELI", "THIRUPPUR", "THIRUVALLUR", "THIRUVANNAMALAI",
                   "THIRUVARUR", "THOOTHUKUDI", "TIRUPPATTAR", "VELLORE", "VILLUPURAM", "VIRUDHUNAGAR"],
    "Puducherry": ["PUDUCHERRY", "KARAIKAL", "YANAM"],
    "Odisha": ["ANUGUL", "BALANGIR", "BALESHWAR", "BARAGARH", "BHADRAK", "BAUDA", "CUTTACK", "DEOGARH", "DHENKANAL", "GAJAPATHI",
               "GANJAM", "JAGATSINGHPUR", "JAJAPUR", "JHARSUGUDA", "KALAHANDI", "KANDHAMAL", "KENDRAPARHA", "KENDUJHAR", "KHORDHA",
               "KORAPUT", "MALKANGIRI", "MAYURBHANJ", "NABARANGAPUR", "NAYAGARH", "NUAPARHA", "PURI", "RAYAGARHA", "SAMBALPUR",
               "SUBARNAPUR", "SUNDARGARH"],
    "Telangana": ["ADILABAD", "B. KOTHAGUDEM", "HANAMKONDA", "HYDERABAD", "J. BHUPALPALLY", "JAGTIAL", "JANGAON", "JOGULAMBA GADWAL",
                  "KAMAREDDY", "KARIMNAGAR", "KHAMMAM", "KUMARAM BHEEM", "MAHABUBABAD", "MAHABUBNAGAR", "MANCHERIAL", "MEDAK",
                  "M. MALKAJGIRI", "MULUGU", "NAGARKURNOOL", "NALGONDA", "NARAYANPET", "NIRMAL", "NIZAMABAD", "PEDDAPALLE",
                  "RAJANNA SIRCILLA", "RANGAREDDY", "SANGAREDDY", "SIDDIPET", "SURYAPET", "VIKARABAD", "WANAPARTHY", "WARANGAL",
                  "Y. BHUVANAGIRI"],
}
_KEEP_CAPS = {"NTR", "SPSR", "YSR", "B.", "J.", "M.", "Y."}


def district_name(n: str) -> str:
    """'EAST GODAVARI' -> 'East Godavari'; IMD's abbreviations (NTR, SPSR, YSR, B.) stay as written."""
    return " ".join(w if w in _KEEP_CAPS else w.capitalize() for w in n.strip().split())


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_bytes(url: str, timeout: float = 60) -> bytes:
    """A PDF, cached on disk forever (IMD's bulletin URLs are unique per issue)."""
    key = CACHE_DIR / "pdf" / (hashlib.sha1(url.encode()).hexdigest() + ".pdf")
    if key.is_file() and key.stat().st_size > 0:
        return key.read_bytes()
    r = _session().get(url, timeout=timeout)
    r.raise_for_status()
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_bytes(r.content)
    return r.content


def _flat(s: str) -> str:
    return " ".join((s or "").split())


def compass(words: str) -> str:
    """'east-southeast' -> 'ESE', 'northwestwards' -> 'NW', 'westwards' -> 'W'."""
    w = re.sub(r"wards?$", "", words.lower().strip())
    out = ""
    for part in w.split("-"):
        for k, v in (("north", "N"), ("south", "S"), ("east", "E"), ("west", "W")):
            part = part.replace(k, v)
        out += part
    return out if re.fullmatch(r"[NSEW]{1,3}", out) else ""


def _date(day: int, month: str | int, year: int) -> str:
    m = month if isinstance(month, int) else MONTHS[month.lower()[:3]]
    return f"{year:04d}-{m:02d}-{day:02d}"


# IMD's "midnight of 2nd" is the night of the 2nd into the 3rd (its own clock time is 2330 IST), so 23, not 0 of the 2nd
_PART_OF_DAY_IST = {"early morning": 5, "morning": 8, "forenoon": 10, "noon": 12, "afternoon": 14, "evening": 18,
                    "night": 21, "midnight": 23}


# ─────────────────────────────────────────────────────────────────────────────
# RSMC home page
# ─────────────────────────────────────────────────────────────────────────────

def rsmc_links(page: str) -> dict:
    """The current bulletin links of RSMC New Delhi's home page (their file names change every issue)."""
    out: dict = {}
    pairs = [(m.group(1), _flat(htmllib.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))))
             for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)]
    want = {"national": ("National Bulletin", "National_Bulletin"), "rsmc": ("RSMC Bulletin", "Tropical_cyclone_advisory"),
            "tcac": ("TCAC Bulletin", "TC_ADVISORY"), "rain": ("Heavy Rainfall", "HEAVY_RAINFALL"),
            "track_png": ("Observed & Forecast Track", "TRACK")}
    for key, (label, fname) in want.items():
        for href, txt in pairs:
            if (txt == label or fname in href) and href.lower().endswith((".pdf", ".png")) and "No Cyclone" not in href:
                out[key] = RSMC + href.lstrip("/").replace(" ", "%20") if not href.startswith("http") else href
                break
    subj = next((txt for href, txt in pairs if "National_Bulletin" in href and len(txt) > 30), "")
    if subj:
        out["subject"] = subj
    return out


# ─────────────────────────────────────────────────────────────────────────────
# National Bulletin
# ─────────────────────────────────────────────────────────────────────────────

def _section(t: str, start: str, ends: list[str]) -> str:
    i = t.find(start)
    if i < 0:
        return ""
    j = min([k for k in (t.find(e, i + len(start)) for e in ends) if k > 0] or [len(t)])
    return t[i + len(start): j].strip()


def _dates_in(s: str, year: int, month_default: int = 10) -> list[str]:
    """'27th & 28th October' / '26th to 29th October' / '28th Oct' -> ISO dates (ranges expanded)."""
    out = []
    for m in re.finditer(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:(&|and|to|-)\s*(\d{1,2})(?:st|nd|rd|th)?\s*)?(October|Oct|November|Nov|December|Dec|September|Sep)\b", s):
        mon = MONTHS[m.group(4).lower()[:3]]
        a = int(m.group(1))
        b = int(m.group(3)) if m.group(3) else a
        days = range(a, b + 1) if m.group(2) in ("to", "-") else sorted({a, b})
        out += [_date(d, mon, year) for d in days]
    return out


_RAIN_LEVELS = ["heavy", "heavy to very heavy", "very heavy", "extremely heavy"]


def _rain_items(sec: str, year: int) -> tuple[list[dict], list[str]]:
    items: dict[tuple, list[str]] = {}
    texts = []
    for m in re.finditer(r"(?:^|\n)([A-Z][A-Za-z &\-]+?):\s*(.+?)(?=\n[A-Z][A-Za-z &\-]+?:|\Z)", sec, re.S):
        area, body = m.group(1).strip(), _flat(m.group(2))
        texts.append(f"{area}: {body}")
        pos = 0
        for dm in re.finditer(r"(?:on|during|till)\s+((?:\d{1,2}(?:st|nd|rd|th)?\s*(?:&|and|to)?\s*)+(?:October|Oct)\b)", body):
            seg = body[pos: dm.end()]
            pos = dm.end()
            lv = [l for l in _RAIN_LEVELS if re.search(rf"\b{l}\b", seg, re.I)]
            if not lv:
                continue
            top = max(lv, key=_RAIN_LEVELS.index)
            sub = re.search(r"over ((?:north|south|east|west|interior|coastal|costal|extreme|eastern|western|northern|southern)[^,;.]*?)"
                            r"(?=\s+(?:is|on|during|and|till)\b|$)", seg)
            where = sub.group(1).strip() if sub and len(sub.group(1)) < 60 else area
            for d in _dates_in(dm.group(1), year):
                items.setdefault((d, top), [])
                if where not in items[(d, top)]:
                    items[(d, top)].append(where)
    rain = [{"date": d, "level": lv, "areas": areas} for (d, lv), areas in sorted(items.items())]
    return rain, texts


def _bullets(sec: str) -> list[str]:
    parts = re.split(r"\n?\s*[•]\s*", sec)
    return [_flat(p) for p in parts if _flat(p)]


def _wind_items(bullets: list[str], year: int) -> list[dict]:
    out = []
    for b in bullets:
        area = re.search(r"(?:over|along\s*(?:&|and)\s*off)\s+(.+?)(?=\s+(?:from|till|by|is|would|and decrease|during|in association|thereafter)\b|[.,;])", b)
        for m in re.finditer(r"(\d+)\s*-\s*(\d+)\s*(?:kmph\s*)?gusting to\s*(\d+)\s*(?:kmph)?", b):
            tail = b[m.end(): m.end() + 200]
            # this speed's own clause: up to the next speed, sentence end or semicolon
            clause = re.split(r"(?:,|\band\b)\s*(?:\w+\s+){0,4}\d+\s*-\s*\d+\s*(?:kmph\s*)?gusting|\.(?:\s|$)|;", tail)[0]
            local = re.match(r"\s*(?:kmph\s*)?\((?:over|along\s*(?:&|and)\s*off)\s+([^)]+)\)", clause)
            dates = _dates_in(clause, year)
            out.append({"date": dates[0] if dates else None, "kmh": [int(m.group(1)), int(m.group(2))], "gust_kmh": int(m.group(3)),
                        "areas": [local.group(1).strip()] if local else ([area.group(1).strip()] if area else []),
                        "when_text": _flat(re.sub(r"^\s*kmph\s*", "", clause))})
    return out


def _fishermen(sec: str, year: int) -> dict:
    items = []
    for b in _bullets(sec):
        if b.lower().startswith("fishermen"):
            continue
        m = re.match(r"(.+?)\s+(?:from|on|till|during)\s+(.+?);?$", b)
        area = (m.group(1) if m else b).strip(" ;")
        dates = _dates_in(m.group(2), year) if m else []
        items.append({"area": area, "from": dates[0] if dates else None, "to": dates[-1] if dates else None})
    tos = [i["to"] for i in items if i["to"]]
    return {"until": max(tos) if tos else None, "areas": [i["area"] for i in items], "items": items, "text": _flat(sec)}


def _surge(sec: str) -> dict:
    s = _flat(sec)
    out = {"text": s}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?)\s*m(?:etre|eter)?s?\b", s)   # "1.0 – 1.5 m" (IMD 2200 IST 2 Nov)
    if m:
        out["m"] = [float(m.group(1)), float(m.group(2))]
    inund = re.search(r"inundate low[- ]lying areas of ([^.]+?)(?: during| at| around| from| with|\.)", s)
    out["areas"] = [a.strip() for a in re.split(r",| and ", inund.group(1)) if a.strip()] if inund else []
    peak = re.search(r"peak surge is expected (?:over|near|along) (.+?)\.", s)
    if peak:
        names, near = [], []
        for part in re.split(r"\s+and\s+(?:also\s+)?|,", peak.group(1)):
            nm = re.search(r"\(near ([^)]+)\)", part)
            if nm:
                near.append(nm.group(1).strip())
            base = re.sub(r"\([^)]*\)|\bdistricts?\b|^(?:also )?(?:over|near|along) ", "", part.strip(), flags=re.I).strip()   # "and also over Krishna"
            if base:
                names.append(base[0].upper() + base[1:])
        out["peak_areas"], out["peak_near"], out["peak_text"] = names, near, peak.group(1)
    return out


_TABLE_ROW = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})/(\d{4})\s+(\d+\.\d+)\s*/\s*(\d+\.\d+)\s+(\d+)\s*-\s*(\d+)\s+gusting to\s+(\d+)\s+"
                        r"([A-Za-z][A-Za-z\- ]+?)\s*(?=\n|\d{2}\.\d{2}\.\d{2}/|$)")


def _table(t: str, tz: timezone) -> list[dict]:
    out = []
    for m in _TABLE_ROW.finditer(t):
        dd, mo, yy, hhmm = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3)), m.group(4)
        when = datetime(yy, mo, dd, int(hhmm[:2]), int(hhmm[2:]), tzinfo=tz).astimezone(timezone.utc)
        cls = _flat(m.group(10))
        out.append({"timeUTC": S.iso(when), "lat": float(m.group(5)), "lon": float(m.group(6)),
                    "wind_kmh": [int(m.group(7)), int(m.group(8))], "gust_kmh": int(m.group(9)), "class": cls,
                    "class_short": CLASS_SHORT.get(cls.lower(), "")})
    return out


def parse_national(t: str) -> dict:
    """IMD National Bulletin (text from its PDF) -> desk.json in.imd fields (sentences + structured)."""
    out: dict = {}
    m = re.search(r"NATIONAL BULLETIN NO\.\s*(\d+)\s*\(([^)]+)\)", t)
    if m:
        out["bulletin"] = f"National Bulletin No. {m.group(1)} ({m.group(2).strip()})"
    m = re.search(r"TIME OF ISSUE:\s*(\d{2})(\d{2})\s*HOURS\s*IST\s*DATED:\s*(\d{2})\.(\d{2})\.(\d{4})", t)
    year = datetime.now(timezone.utc).year
    if m:
        hh, mi, dd, mo, year = map(int, m.groups())
        issued = datetime(year, mo, dd, hh, mi, tzinfo=IST)
        out["issuedUTC"] = S.iso(issued.astimezone(timezone.utc))
        out["issued_ist_text"] = f"{hh:02d}{mi:02d} hrs IST of {dd} {issued:%B} {year}"
    sub = re.search(r"Sub\s*:\s*(.+?)\n\s*\n", t, re.S)
    if sub:
        out["subject"] = _flat(sub.group(1))
        col = re.search(r"(Red|Orange|Yellow|Green) Message", out["subject"])
        if col:
            out["message"] = col.group(1).lower()
    main = re.search(rf"The {_CLASS_RX}\b(.+?)(?=\n\s*\n|\nIt is very likely|\nThereafter)", t, re.S | re.I)
    if main:
        para = _flat(main.group(0))
        cls = re.search(rf"intensified into an? {_CLASS_RX}", para, re.I)      # "The Cyclonic Storm ... intensified into a severe cyclonic storm"
        cls = (cls or main).group(1)
        out["class"] = cls.title()
        out["class_short"] = CLASS_SHORT.get(cls.lower(), "")
        # "moved west-northwestwards with a speed of 13 kmph", also "moved nearly northwestwards with speed of 20 kmph"
        mv = re.search(r"moved (?:(?:nearly|slowly|almost) )?([a-z\-]+?) with (?:a )?speed of (\d+) kmph during (?:the )?past (\d+) hours", para)
        if mv:
            out["movement_text"] = mv.group(0)
            out["movement"] = {"dir": compass(mv.group(1)), "kmh": int(mv.group(2)), "hours": int(mv.group(3))}
        elif re.search(r"remained (?:practically )?stationary", para):
            out["movement_text"] = "remained practically stationary"
            out["movement"] = {"dir": "", "kmh": 0}
        at = re.search(r"cent(?:ere|re|er)d at (\d{2})(\d{2}) (?:hrs|hours) IST of (?:today,? |yesterday,? )?(?:the )?(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]+),? (\d{4})", para)
        if at:
            obs = datetime(int(at.group(5)), MONTHS[at.group(4).lower()[:3]], int(at.group(3)), int(at.group(1)), int(at.group(2)), tzinfo=IST)
            out["observedUTC"] = S.iso(obs.astimezone(timezone.utc))
        ll = re.search(r"latitude\s*(\d+\.\d+)\s*°?\s*N\s*and longitude\s*(\d+\.\d+)\s*°?\s*E", para, re.I)
        if ll:
            out["lat"], out["lon"] = float(ll.group(1)), float(ll.group(2))
            tail = para[ll.end():].strip(" ,")
            out["position_text"] = tail.rstrip(" ,.")
            out["position"] = [{"km": int(k), "dir": compass(d), "place": p.strip(), **({"state": s} if s else {})}
                               for k, d, p, s in re.findall(r"(\d+)\s*km\s+([a-z\-]+)\s+of\s+([A-Z][A-Za-z .']+?)\s*(?:\(([^)]+)\))?(?=,|\s+and\b|$)", out["position_text"])]
    after = t[main.end():] if main else t
    outlook = _flat(after.split("Forecast location")[0])
    out["outlook_text"] = [x.strip() for x in re.split(r"(?<=\.)\s+", outlook) if x.strip(" .")][:4]
    lf = re.search(r"[^.]*\bcross\b[^.]*\bcoasts?\b[^.]*\.", outlook)
    if lf:
        s = lf.group(0).strip()
        out["landfall_text"] = s
        land = {}
        bt = re.search(r"between ([A-Z][A-Za-z .]+?) and ([A-Z][A-Za-z .]+?)(?=\s+(?:close to|near|as|with|by|around|during)\b|,)", s)
        if bt:
            land["between"] = [bt.group(1).strip(), bt.group(2).strip()]
        nr = re.search(r"(?:close to|near) ([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)", s)
        if nr:
            land["near"] = nr.group(1)
        else:                                    # "to the south of Ongole" (IMD 1145 IST 2 Nov): the town and the side of it
            rel = re.search(r"to the (north|south|east|west)(?:-?(?:east|west))? of ([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)", s)
            if rel:
                land["near"], land["near_rel"] = rel.group(2), rel.group(1)
        cl = re.search(rf"as an? {_CLASS_RX}", s, re.I)
        if cl:
            land["class"] = cl.group(1).title()
            land["class_short"] = CLASS_SHORT.get(cl.group(1).lower(), "")
        w = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*kmph gusting (?:to )?(\d+)\s*kmph", s)
        if w:
            land["wind_kmh"], land["gust_kmh"] = [int(w.group(1)), int(w.group(2))], int(w.group(3))
        tm = re.search(r"(?:by|during|around|on|in the)\s+(?:the\s+)?(early morning|morning|forenoon|noon|afternoon|evening|night|midnight)\s+of\s+"
                       r"(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:,?\s*(\d{4}))?", s)
        # "during midnight (2330 Hrs IST) of 2nd to early hours (0400 Hrs IST) of 3rd November, 2026": IMD's own clock times
        clk = list(re.finditer(r"(?:(early morning|early hours|morning|forenoon|noon|afternoon|evening|night|midnight)\s*)?"
                               r"\((\d{2})(\d{2})\s*hrs?\s*IST\)\s*of\s*(?:(?:today|tomorrow|yesterday),?\s*)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:\s+([A-Za-z]+))?", s, re.I))
        mon = next((x for x in re.findall(r"\b([A-Z][a-z]+)\b", s[clk[0].start():]) if x.lower()[:3] in MONTHS), None) if clk else None
        if clk and mon:
            yr = re.search(rf"{mon},?\s*(\d{{4}})", s)
            yr = int(yr.group(1)) if yr else year
            ends = []
            for c in clk[:2]:
                m_ = c.group(5) if c.group(5) and c.group(5).lower()[:3] in MONTHS else mon
                d = _date(int(c.group(4)), m_, yr)
                at_ = datetime.fromisoformat(d).replace(hour=int(c.group(2)), minute=int(c.group(3)), tzinfo=IST)
                ends.append((d, f"{c.group(2)}{c.group(3)}", S.iso(at_.astimezone(timezone.utc)), (c.group(1) or "").lower()))
            land["date"], land["time_ist"], land["timeUTC"] = ends[0][:3]
            land["time_basis"] = f"IMD National Bulletin ({ends[0][1]} IST)"
            if ends[0][3] in _PART_OF_DAY_IST:
                land["part_of_day"] = ends[0][3]
            if len(ends) > 1:
                land["until"] = {"date": ends[1][0], "time_ist": ends[1][1], "timeUTC": ends[1][2]}
            land["time_text"] = " to ".join(f"{e[1]} IST of {int(e[0][8:])} {mon}" for e in ends)
        elif tm:
            land["part_of_day"] = tm.group(1)
            land["date"] = _date(int(tm.group(2)), tm.group(3), int(tm.group(4) or year))
            land["time_text"] = f"{tm.group(1)} of {int(tm.group(2))} {tm.group(3)}"
        out["landfall"] = land
    # after landfall IMD reports it in the main paragraph: "crossed south Andhra Pradesh coast between Nellore and
    # Narasapur close to Ongole (near Latitude ...) during 0330 to 0530 hours IST with the wind speed of 100-110 kmph
    # gusting to 120 kmph" (0730 IST 3 Nov). That replaces any forecast landfall.
    _in_sentence = r"(?:(?!\.\s).)*?"      # within one sentence; decimals like 15.53 do not end it
    crossed = re.search(r"crossed " + _in_sentence + r"coast between ([A-Z][a-z]+(?: [A-Z][a-z]+)?) and ([A-Z][a-z]+(?: [A-Z][a-z]+)?)"
                        r"(?:,?\s+(?:close to|near) ([A-Z][A-Za-z]+))?" + _in_sentence +
                        r"during (\d{4})\s*(?:to|-)\s*(\d{4})\s*(?:[Hh]rs|[Hh]ours)\s*IST", _flat(t))
    if crossed:
        s2 = _flat(t)[crossed.start():crossed.start() + 600]
        land = {"crossed": True, "between": [crossed.group(1).strip(), crossed.group(2).strip()],
                "crossed_ist": [crossed.group(4), crossed.group(5)], "crossed_text": _flat(crossed.group(0))}
        if crossed.group(3):
            land["near"] = crossed.group(3)
        w = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*kmph gusting (?:to )?(\d+)\s*kmph", s2)
        if w:
            land["wind_kmh"], land["gust_kmh"] = [int(w.group(1)), int(w.group(2))], int(w.group(3))
        out["landfall"] = land
    tz = IST if re.search(r"Date/Time\s*\(IST\)", t) else timezone.utc
    out["forecast"] = _table(t, tz)
    if out["forecast"]:
        f0 = out["forecast"][0]
        out["wind_kmh"], out["gust_kmh"] = f0["wind_kmh"], f0["gust_kmh"]
        out["wind_text"] = f"{f0['wind_kmh'][0]}-{f0['wind_kmh'][1]} kmph gusting to {f0['gust_kmh']} kmph"
    ends = ["(ii)", "(iii)", "(iv)", "(v)", "(vi)", "(vii)"]
    rain_sec = _section(t, "Heavy Rainfall Warning:", ends)
    out["rain"], out["rain_text"] = _rain_items(rain_sec, year) if rain_sec else ([], [])
    wind_sec = _section(t, "Wind warning:", ["(iii)", "(iv)", "(v)", "(vi)"])
    wb = _bullets(wind_sec)
    out["wind_warnings_text"] = wb
    out["wind_warnings"] = _wind_items(wb, year)
    sea_sec = _section(t, "Sea condition:", ["(iv)", "(v)", "(vi)"])
    out["sea"] = _bullets(sea_sec)
    out["sea_text"] = " ".join(out["sea"])
    surge_sec = _section(t, "Storm Surge Warning:", ["(v)", "(vi)"])
    if surge_sec:
        out["surge"] = _surge(surge_sec)
        out["surge_text"] = out["surge"]["text"]
    fish_sec = _section(t, "Fisherman warning:", ["(vi)", "(vii)"]) or _section(t, "Fishermen warning:", ["(vi)", "(vii)"])
    if fish_sec:
        out["fishermen"] = _fishermen(fish_sec, year)
        out["fishermen_text"] = out["fishermen"]["text"]
    imp = _section(t, "(vi) Impact Expected", ["(vii)", "\n\n\n"])
    if imp:
        out["impact_text"] = [_flat(x) for x in re.split(r"\n(?=[–\-•]|\([a-z]\))", imp) if _flat(x) and not _flat(x).startswith("and ")][:30]
    nb = re.search(r"Next (?:Message|bulletin) will be issued at (\d{2})(\d{2})\s*(?:hours|hrs)\s*IST[^.]*?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s*(\d{4})", t, re.I)
    if nb:
        nxt = datetime(int(nb.group(5)), MONTHS[nb.group(4).lower()[:3]], int(nb.group(3)), int(nb.group(1)), int(nb.group(2)), tzinfo=IST)
        out["next_bulletin"] = {"timeUTC": S.iso(nxt.astimezone(timezone.utc)), "text": _flat(nb.group(0)) + "."}
    out["by_state"] = _by_state(out)
    return out


_STATES = ["Andhra Pradesh", "Tamil Nadu", "Odisha", "Puducherry", "Yanam", "Telangana", "West Bengal", "Chhattisgarh"]


def _by_state(imd: dict) -> dict:
    """Every IMD warning sentence that names a state (Tamil Nadu items for the ta stream, AP for te)."""
    sents = list(imd.get("rain_text") or []) + list(imd.get("wind_warnings_text") or []) + list(imd.get("sea") or [])
    sents += [imd.get("surge_text") or "", imd.get("fishermen_text") or ""]
    out: dict[str, list[str]] = {}
    for s in sents:
        for st in _STATES:
            if st.lower() in (s or "").lower():
                out.setdefault(st, []).append(s)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# RSMC advisory, TCAC, district warnings
# ─────────────────────────────────────────────────────────────────────────────

def parse_rsmc(t: str) -> dict:
    out = {}
    m = re.search(r"cross[^.]*?by\s*(\d{2})(\d{2})\s*UTC\s*of\s*(?:the\s*)?(\d{1,2})(?:st|nd|rd|th)?\s*([A-Za-z]+),?\s*(\d{4})?", t)
    if m:
        y = int(m.group(5) or datetime.now(timezone.utc).year)
        out["landfall_timeUTC"] = S.iso(datetime(y, MONTHS[m.group(4).lower()[:3]], int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc))
    p = re.search(r"estimated central pressure is (\d{3,4})\s*hPa and maximum sustained wind speed is (\d+)\s*kt", t)
    if p:
        out["pressure_hpa"], out["pressure_wind_kt"] = float(p.group(1)), int(p.group(2))
    return out


def parse_tcac(t: str) -> dict:
    out = {}
    m = re.search(r"DTG:\s*(\d{4})(\d{2})(\d{2})/(\d{2})(\d{2})Z", t)
    if m:
        out["timeUTC"] = S.iso(datetime(*map(int, m.groups()), tzinfo=timezone.utc))
    p = re.search(r"\bC:\s*(\d{3,4})\s*HPA", t)
    w = re.search(r"MAX WIND:\s*(\d+)\s*KT", t)
    if p:
        out["pressure_hpa"] = float(p.group(1))
    if w:
        out["wind_kt"] = int(w.group(1))
    return out


def parse_districts(doc: dict) -> dict:
    """IMD district warnings (WFS, attributes only) -> {"issued", "days": [dates], "states": {state: {district: [day1..3]}}}."""
    feats = doc.get("features") or []
    if not feats:
        raise ValueError("no district warning features")
    to_state = {d: s for s, ds in STATE_DISTRICTS.items() for d in ds}
    p0 = feats[0]["properties"]
    base = datetime.fromisoformat(p0["Date"]).date()
    days = [(base + timedelta(days=k)).isoformat() for k in range(3)]
    states: dict[str, dict] = {}
    for f in feats:
        p = f["properties"]
        st = to_state.get((p.get("District") or "").strip())
        if not st:
            continue
        cells = []
        for k in (1, 2, 3):
            codes = [c for c in str(p.get(f"Day_{k}") or "").split(",") if c.strip()]
            cells.append({"date": days[k - 1], "colour": DISTRICT_COLOUR.get(p.get(f"Day{k}_Color"), ""),
                          "hazards": [DISTRICT_HAZARD.get(c.strip(), c.strip()) for c in codes if c.strip() != "1"]})
        states.setdefault(st, {})[district_name(p["District"])] = cells
    upd = max((f["properties"].get("updated_at") or "") for f in feats)
    return {"issued": f"{p0['Date']} {int(p0.get('UTC') or 0):02d}00 UTC", "updated_at": upd, "days": days, "states": states}


def jtwc_past(tcw: str) -> list[dict]:
    """IO past track lines ("0226102118 118N 887E  20"): storm no, yymmddhh, position (a space between lat and lon), kt."""
    seen, out = set(), []
    for l in tcw.splitlines():
        m = re.match(r"^\d{2}(\d{8})\s+(\d+[NS])\s*(\d+[EW])\s+(\d+)\s*$", l.strip())
        if m:
            when = datetime.strptime(m.group(1), "%y%m%d%H").replace(tzinfo=timezone.utc)
            if when in seen:
                continue
            seen.add(when)
            out.append({"timeUTC": S.iso(when), "lat": S._ll(m.group(2)), "lon": S._ll(m.group(3)), "wind_kt": float(m.group(4))})
    return sorted(out, key=lambda p: p["timeUTC"])


def jtwc_nio(jtwc_id: str) -> dict:
    tcw = get_text(f"{S.JTWC_PRODUCTS}/{jtwc_id}.tcw")
    web = get_text(f"{S.JTWC_PRODUCTS}/{jtwc_id}web.txt")
    out = S.parse_jtwc(tcw, web, jtwc_id)
    if not out.get("past"):
        out["past"] = jtwc_past(tcw)
    return out


def jtwc_active_nio() -> list[dict]:
    return [a for a in S.jtwc_active() if a["id"].startswith(("io", "sh"))]


def imd_bulletin() -> dict:
    """Fetch and parse RSMC New Delhi's current products. Raises if the National Bulletin can't be read."""
    links = rsmc_links(get_text(RSMC))
    if "national" not in links:
        raise RuntimeError("RSMC home page lists no National Bulletin")
    imd = parse_national(pdf_text(get_bytes(links["national"])))
    imd["source_url"] = links["national"]
    if links.get("subject"):
        imd.setdefault("subject", links["subject"])
    if links.get("track_png"):
        imd["track_image_url"] = links["track_png"]
    for key, parse in (("rsmc", parse_rsmc), ("tcac", parse_tcac)):
        if links.get(key):
            try:
                imd["_" + key] = parse(pdf_text(get_bytes(links[key])))
                imd["_" + key]["url"] = links[key]
            except Exception as e:  # noqa: BLE001 - the National Bulletin is enough
                log.warning("IMD %s bulletin unreadable: %s", key, e)
    return imd


def district_warnings() -> dict:
    import json

    return parse_districts(json.loads(get_text(DISTRICT_WFS, ttl=600)))

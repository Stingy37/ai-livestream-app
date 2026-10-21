"""Reference cities (a copy of the page's static city list) and closest-point-of-approach maths.

Used to pick each impact column's "closest pass" towns and to publish the CPA of every city along
the official forecast track (``cpa`` in desk.json), which the page uses for its CPA zooms.
Keep CITIES in step with the ``cities`` list in html/champi-desk.html.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

CITIES = [
    {"n": "Manila", "lat": 14.60, "lon": 120.98, "cc": "PH"}, {"n": "Legazpi", "lat": 13.14, "lon": 123.74, "cc": "PH"},
    {"n": "Virac", "lat": 13.58, "lon": 124.23, "cc": "PH"}, {"n": "Aparri", "lat": 18.36, "lon": 121.63, "cc": "PH"},
    {"n": "Basco", "lat": 20.45, "lon": 121.97, "cc": "PH"}, {"n": "Taipei", "lat": 25.03, "lon": 121.56, "cc": "TW"},
    {"n": "Yilan", "lat": 24.75, "lon": 121.75, "cc": "TW"}, {"n": "Hualien", "lat": 23.98, "lon": 121.60, "cc": "TW"},
    {"n": "Taitung", "lat": 22.76, "lon": 121.14, "cc": "TW"}, {"n": "Yonaguni", "lat": 24.47, "lon": 123.00, "cc": "JP"},
    {"n": "Ishigaki", "lat": 24.34, "lon": 124.16, "cc": "JP"}, {"n": "Miyakojima", "lat": 24.80, "lon": 125.28, "cc": "JP"},
    {"n": "Naha", "lat": 26.21, "lon": 127.68, "cc": "JP"}, {"n": "Guam", "lat": 13.44, "lon": 144.79, "cc": "US"},
]


def dist_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def closest_approach(track: list[dict], lat: float, lon: float, steps: int = 60) -> dict | None:
    """Closest point of a track (dicts with lat, lon, timeUTC) to a place, linear in lat/lon and time."""
    if len(track) < 2:
        return None
    best = None
    for a, b in zip(track, track[1:]):
        ta = datetime.fromisoformat(a["timeUTC"].replace("Z", "+00:00")).timestamp()
        tb = datetime.fromisoformat(b["timeUTC"].replace("Z", "+00:00")).timestamp()
        for k in range(steps + 1):
            s = k / steps
            p = (a["lat"] + (b["lat"] - a["lat"]) * s, a["lon"] + (b["lon"] - a["lon"]) * s)
            d = dist_km(p, (lat, lon))
            if best is None or d < best["km"]:
                best = {"km": d, "lat": p[0], "lon": p[1], "t": ta + (tb - ta) * s}
    best["timeUTC"] = datetime.fromtimestamp(best.pop("t"), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    best["km"] = round(best["km"])
    best["lat"], best["lon"] = round(best["lat"], 2), round(best["lon"], 2)
    return best


def cpa_table(track: list[dict]) -> list[dict]:
    out = []
    for c in CITIES:
        ca = closest_approach(track, c["lat"], c["lon"])
        if ca:
            out.append({"city": c["n"], "cc": c["cc"], "lat": c["lat"], "lon": c["lon"], "km": ca["km"],
                        "timeUTC": ca["timeUTC"], "track_lat": ca["lat"], "track_lon": ca["lon"]})
    return sorted(out, key=lambda x: x["km"])


def passes_by_country(cpa: list[dict], per_country: int = 2) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in cpa:                       # already sorted by distance
        lst = out.setdefault(row["cc"], [])
        if len(lst) < per_country:
            lst.append(row["city"])
    return out

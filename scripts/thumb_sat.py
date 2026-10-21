"""Fetch the thumbnail's hero image: Himawari-9's rapid-scan target sector (2.5-minute, ~1000 km box that JMA points
at the typhoon) from CIRA RAMMB SLIDER, located on the full disk so the storm center and forecast track can be drawn on it.

    /home/andyshi2/.conda/envs/ai-livestream/bin/python scripts/thumb_sat.py [--product auto|geocolor|ir] [--desk output/desk/desk.json]

Writes html/thumb/hero.jpg + hero.json (time, product, the JMA center and forecast points in image pixels, credit),
which html/thumb-hero.html draws. auto = GeoColor while the sun is up over the storm, enhanced infrared after dark.
Exits non-zero (and writes nothing) when the sector is not on the storm, so the caller can fall back to the map thumbnail.

Locating the sector: SLIDER serves the sector and the full disk on the same fixed Himawari grid, so the sector's
infrared at 2 km is matched against the full-disk infrared around the storm (FFT cross-correlation) to find its offset.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

REPO = Path(__file__).resolve().parents[1]
SLIDER = "https://slider.cira.colostate.edu/data"
SECTOR = "mesoscale_01"
FD_TILE, SEC_TILE = 688, 500
SUB_LON = 140.7                       # Himawari-9 sub-satellite longitude
CFAC, COFF = 20466275, 2750.5         # 2 km fixed grid (5500 x 5500), JMA HSD navigation
OUT_DIR = REPO / "html" / "thumb"
# enhanced infrared on SLIDER's band 13 data values (the PNG palette indices: higher = colder; clear sea ~75, the eyewall's
# coldest tops ~220): gray below the cloud tops, then the usual typhoon ramp blue > green > yellow > red > magenta > white
IR_STOPS = [(0, (10, 14, 22)), (110, (128, 134, 144)), (125, (40, 80, 190)), (150, (40, 170, 230)), (170, (60, 200, 90)),
            (186, (240, 225, 60)), (198, (255, 140, 30)), (207, (230, 30, 40)), (214, (205, 30, 165)), (220, (255, 185, 240)),
            (226, (255, 255, 255)), (255, (255, 255, 255))]


def get(url: str, timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "typhoon-desk-thumbnail/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def times(sector: str, product: str) -> list[int]:
    return json.loads(get(f"{SLIDER}/json/himawari/{sector}/{product}/latest_times.json"))["timestamps_int"]


def tile(sector: str, product: str, ts: int, level: int, row: int, col: int) -> Image.Image | None:
    s = str(ts)
    url = f"{SLIDER}/imagery/{s[:4]}/{s[4:6]}/{s[6:8]}/himawari---{sector}/{product}/{s}/{level:02d}/{row:03d}_{col:03d}.png"
    try:
        return Image.open(io.BytesIO(get(url)))
    except OSError:
        return None


def sector_image(product: str, ts: int, level: int) -> Image.Image:
    """The sector at one zoom level: RGB for imagery products, raw data values (mode L) for single bands."""
    n, mode = 2 ** level, "RGB" if product == "geocolor" else "L"
    im = None
    for r in range(n):
        for c in range(n):
            t = tile(SECTOR, product, ts, level, r, c)
            if t is None:
                continue
            if im is None:
                im = Image.new(mode, (SEC_TILE * n, SEC_TILE * n))
            im.paste(t.convert("RGB") if mode == "RGB" else Image.fromarray(np.asarray(t)), (c * SEC_TILE, r * SEC_TILE))
    if im is None:
        raise RuntimeError(f"no {product} tiles for {ts} level {level}")
    return im


def geos(lat: float, lon: float) -> tuple[float, float]:
    """(column, line) on the 2 km full-disk grid, 0-based pixel centers (JMA HSD navigation)."""
    phi = math.atan(0.993305616 * math.tan(math.radians(lat)))
    rl = 6356.7523 / math.sqrt(1 - 0.00669438444 * math.cos(phi) ** 2)
    dl = math.radians(lon - SUB_LON)
    r1 = 42164 - rl * math.cos(phi) * math.cos(dl)
    r2 = -rl * math.cos(phi) * math.sin(dl)
    r3 = rl * math.sin(phi)
    rn = math.sqrt(r1 * r1 + r2 * r2 + r3 * r3)
    x, y = math.degrees(math.atan(-r2 / r1)), math.degrees(math.asin(-r3 / rn))
    return COFF + x * CFAC / 2 ** 16 - 1, COFF + y * CFAC / 2 ** 16 - 1


def sun_elev(lat: float, lon: float, when: datetime) -> float:
    t = when.timestamp() / 86400 + 2440587.5 - 2451545.0
    g = math.radians(357.529 + 0.98560028 * t)
    q = 280.459 + 0.98564736 * t
    L = math.radians(q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    e = math.radians(23.439 - 0.00000036 * t)
    ra = math.atan2(math.cos(e) * math.sin(L), math.cos(L))
    dec = math.asin(math.sin(e) * math.sin(L))
    gmst = (18.697374558 + 24.06570982441908 * t) % 24
    ha = math.radians(gmst * 15 + lon) - ra
    la = math.radians(lat)
    return math.degrees(math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha)))


def ts_time(ts: int) -> datetime:
    return datetime.strptime(str(ts), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def locate(ts: int, lat: float, lon: float) -> tuple[int, int, float]:
    """Offset (column, line) of the sector's top-left on the 2 km grid, and the match correlation (0..1).
    ts must be a time both the sector and the full disk have (clouds change in minutes)."""
    sec = np.asarray(sector_image("band_13", ts, 0), dtype=np.float64)
    c, l = geos(lat, lon)
    scale = FD_TILE * 8 / 5500                               # level 3 is 5504 px for the 5500 px grid
    half = 800
    x0, y0 = int(c * scale) - half, int(l * scale) - half
    region = np.zeros((2 * half, 2 * half))
    for row in range(max(0, y0 // FD_TILE), min(7, (y0 + 2 * half) // FD_TILE) + 1):
        for col in range(max(0, x0 // FD_TILE), min(7, (x0 + 2 * half) // FD_TILE) + 1):
            t = tile("full_disk", "band_13", ts, 3, row, col)
            if t is None:
                continue
            a = np.asarray(t, dtype=np.float64)          # data values (palette indices)
            ty, tx = row * FD_TILE - y0, col * FD_TILE - x0
            ys, xs = slice(max(0, ty), min(2 * half, ty + FD_TILE)), slice(max(0, tx), min(2 * half, tx + FD_TILE))
            region[ys, xs] = a[ys.start - ty:ys.stop - ty, xs.start - tx:xs.stop - tx]
    h, w = sec.shape
    s = (sec - sec.mean()) / (sec.std() or 1)
    pad = np.zeros_like(region)
    pad[:h, :w] = s
    corr = np.real(np.fft.ifft2(np.fft.fft2(region - region.mean()) * np.conj(np.fft.fft2(pad))))
    corr[2 * half - h + 1:, :] = -np.inf                    # only placements fully inside the region
    corr[:, 2 * half - w + 1:] = -np.inf
    dy, dx = np.unravel_index(np.argmax(corr), corr.shape)
    win = region[dy:dy + h, dx:dx + w]
    r = float(np.corrcoef(win.ravel(), sec.ravel())[0, 1])
    return round((x0 + dx) / scale), round((y0 + dy) / scale), r


def ir_color(im: Image.Image, size: int) -> Image.Image:
    """Enhanced infrared (IR_STOPS), upsampled to size x size before coloring so the color edges stay smooth."""
    g = np.asarray(Image.fromarray(np.asarray(im, dtype=np.float32)).resize((size, size), Image.LANCZOS), dtype=np.float64)
    xs = [x for x, _ in IR_STOPS]
    rgb = np.stack([np.interp(g, xs, [c[i] for _, c in IR_STOPS]) for i in range(3)], axis=-1)
    return Image.fromarray(rgb.clip(0, 255).astype(np.uint8))


def treat_geocolor(im: Image.Image) -> Image.Image:
    """Daylight GeoColor straight from the satellite reads flat white at thumbnail size: pull the midtones down and add
    local contrast so the eye wall, the overshooting tops and the spiral bands carry. Tone only, nothing added or moved."""
    a = np.asarray(im, dtype=np.float64) / 255.0
    a = a ** 2.1                                             # deepen midtones (bright cloud tops stay bright)
    a = a * a * (3 - 2 * a) * 0.55 + a * 0.45                # gentle S-curve for punch
    a = a * np.array([0.92, 0.98, 1.08])                     # cool shadows: sea and cloud gaps read deep blue
    out = Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.UnsharpMask(radius=90, percent=120, threshold=0))  # large-radius "clarity"
    out = out.filter(ImageFilter.UnsharpMask(radius=3, percent=70, threshold=2))
    return ImageEnhance.Color(out).enhance(1.35)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--product", default="auto", choices=["auto", "geocolor", "ir"])
    ap.add_argument("--desk", default=str(REPO / "output" / "desk" / "desk.json"), help="desk.json path or URL (storm center, forecast)")
    ap.add_argument("--min-corr", type=float, default=0.6)
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args()

    raw = get(a.desk) if a.desk.startswith("http") else Path(a.desk).read_bytes()
    desk = json.loads(raw)
    c = desk["center"]
    # newest time both the sector and the full disk have: locate and draw from that one frame, so a sector that
    # JMA re-aimed a few minutes later can never be drawn with a stale offset
    fd = set(times("full_disk", "band_13"))
    ts = next(t for t in times(SECTOR, "band_13") if t in fd)
    when = ts_time(ts)
    product = a.product if a.product != "auto" else ("geocolor" if sun_elev(c["lat"], c["lon"], when) > 12 else "ir")

    ox, oy, r = locate(ts, c["lat"], c["lon"])
    cx, cy = geos(c["lat"], c["lon"])
    ex, ey = cx - ox, cy - oy                               # storm center in sector pixels at 2 km
    if r < a.min_corr or not (40 <= ex <= 460 and 40 <= ey <= 460):
        print(f"rapid-scan sector is not on the storm (match r={r:.2f}, center at {ex:.0f},{ey:.0f} of 500)", file=sys.stderr)
        return 2

    if product == "geocolor":
        img, k = treat_geocolor(sector_image("geocolor", ts, 2)), 4.0          # level 2: 2000 px, 0.5 km
    else:
        img, k = ir_color(sector_image("band_13", ts, 0), 1500), 3.0           # 2 km is the finest; drawn at 1500 px
    shot = when

    pts = []
    for p in (desk.get("forecast") or {}).get("points") or []:
        fx, fy = geos(p["lat"], p["lon"])
        pts.append({"timeUTC": p["timeUTC"], "x": round((fx - ox) * k, 1), "y": round((fy - oy) * k, 1)})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"hero_{product}.jpg"
    img.save(out / f".{name}.tmp", format="JPEG", quality=92)       # renames: streams rendering at once never see a half file
    os.replace(out / f".{name}.tmp", out / name)
    info = {
        "image": name, "product": product, "time": shot.isoformat().replace("+00:00", "Z"),
        "width": img.width, "height": img.height, "km_per_px": 2.0 / k,
        "center": {"x": round(ex * k, 1), "y": round(ey * k, 1), "lat": c["lat"], "lon": c["lon"], "timeUTC": c.get("timeUTC")},
        "forecast": pts, "match": round(r, 3), "sector_offset_2km": [ox, oy],
        "credit": "Himawari-9 (JMA) · CIRA RAMMB SLIDER",
    }
    (out / ".hero.json.tmp").write_text(json.dumps(info, indent=2), encoding="utf-8")
    os.replace(out / ".hero.json.tmp", out / "hero.json")
    print(json.dumps({k2: info[k2] for k2 in ("image", "product", "time", "center", "match")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

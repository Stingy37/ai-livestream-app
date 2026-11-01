"""Render the YouTube thumbnail from live data.

    /home/andyshi2/.conda/envs/ai-livestream/bin/python scripts/youtube_thumbnail.py --lang ja [--style hero|map] [--out output/youtube/thumb_ja.jpg]

Two styles (THUMB_STYLE, default hero):
- hero: Himawari-9's rapid-scan image of the storm fills the frame (scripts/thumb_sat.py fetches it from CIRA RAMMB SLIDER),
  with the motion arrow, the home agency's big number and a headline built from the desk (html/thumb-hero.html; ja, zh, tl, en).
  Falls back to map when the rapid-scan sector is not on the storm. THUMB_SAT_PRODUCT: ir (default, day and night),
  geocolor (true color, daylight only) or auto (geocolor while the sun is up over the storm).
- map: the stream page in thumbnail mode (html/champi-desk.html ?thumb=1).

The map page draws the newest Himawari infrared frame, the official track and cone, and a headline built from the
desk (JMA intensity class, the towns the forecast center passes closest), then sets body[data-thumb-ready] to a
JSON summary of what it drew. This script loads it in headless Chromium inside the encoder container (yt-encoder,
over the DevTools protocol), waits for that flag, and saves a 1920x1080 JPEG under YouTube's 2 MB limit plus a
.json with the summary (scripts/youtube_live.py builds the title from it). Needs the preview server (port 8095).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websockets

REPO = Path(__file__).resolve().parents[1]
UDOCKER = os.environ.get("UDOCKER", "/home/andyshi2/.local/bin/udocker")
os.environ.setdefault("UDOCKER_CONTAINERS", os.path.expanduser("~/.udocker/containers-persist"))   # scripts/encoder/build.sh
PREVIEW = f"http://127.0.0.1:{os.environ.get('PREVIEW_PORT', '8095')}/"


def stream_page() -> str:
    """The preview page of the stream in EC2_STREAM_ID (/s/<id>/), or the default page."""
    sid = os.environ.get("EC2_STREAM_ID", "").strip()
    return PREVIEW + (f"s/{sid}/" if sid and sid != "default" else "")
CDP_PORT = int(os.environ.get("THUMB_CDP_PORT", "9333"))
MAX_BYTES = 2 * 1024 * 1024


async def _capture(ws_url: str, url: str, out: Path, timeout: float) -> dict:
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        seq = 0

        async def call(method: str, **params):
            nonlocal seq
            seq += 1
            await ws.send(json.dumps({"id": seq, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == seq:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    return msg.get("result", {})

        await call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
        await call("Network.enable")
        await call("Network.setCacheDisabled", cacheDisabled=True)   # always the page on disk, never a cached copy
        await call("Page.enable")
        await call("Page.navigate", url=url)
        deadline = time.time() + timeout
        ready = ""
        while time.time() < deadline:
            r = await call("Runtime.evaluate", expression="document.body && document.body.dataset.thumbReady || ''", returnByValue=True)
            ready = r.get("result", {}).get("value") or ""
            if ready:
                break
            r = await call("Runtime.evaluate", expression="document.body && document.body.dataset.thumbError || ''", returnByValue=True)
            if r.get("result", {}).get("value"):
                raise RuntimeError(f"thumbnail page failed: {r['result']['value']}")
            await asyncio.sleep(1)
        if not ready:
            raise TimeoutError(f"the page did not report thumbnail-ready within {timeout:.0f}s ({url})")
        await asyncio.sleep(1.0)                    # let the last fade finish
        for quality in (90, 82, 74, 66):
            shot = await call("Page.captureScreenshot", format="jpeg", quality=quality, fromSurface=True)
            data = base64.b64decode(shot["data"])
            if len(data) <= MAX_BYTES:
                break
        out.write_bytes(data)
        return json.loads(ready)


def hero_ready() -> bool:
    """Fetch the newest rapid-scan image for the hero style; False when it is not usable (not on the storm, SLIDER down)."""
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "thumb_sat.py"), "--desk", stream_page() + "live/desk.json",
                        "--product", os.environ.get("THUMB_SAT_PRODUCT", "ir")], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"hero image unavailable, using the map thumbnail: {(r.stderr or r.stdout).strip()[-300:]}", file=sys.stderr)
    return r.returncode == 0


TW_TEXT = Path(os.environ.get("THUMB_TW_TEXT", REPO / "output" / "youtube" / "thumb_tw_text.json"))


def tw_ready(desk: str | None = None, frame: str = "tw") -> bool:
    """Fetch the storm-and-land infrared frame for the tw style (scripts/thumb_sat.py --frame tw | india)."""
    desk = desk or os.environ.get("THUMB_DESK") or stream_page() + "live/desk.json"
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "thumb_sat.py"), "--frame", frame, "--desk", desk],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"Taiwan frame unavailable: {(r.stderr or r.stdout).strip()[-300:]}", file=sys.stderr)
    return r.returncode == 0


def jma_point_time(place: str) -> str:
    """The time of JMA's own forecast point nearest ``place`` ("23日21時 与那国島の西約60km"), from desk.json jp.forecast;
    "" when JMA names no forecast point by that place (the thumbnail then drops its countdown). JMA's forecast, not ours."""
    src = os.environ.get("THUMB_DESK") or stream_page() + "live/desk.json"
    try:
        desk = json.load(urllib.request.urlopen(src, timeout=15)) if src.startswith("http") else json.loads(Path(src).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    pts = [(0 if "付近" in f["location"] else int(m.group(1)) if (m := re.search(r"約\s*(\d+)\s*km", f["location"])) else 9999, f["time"])
           for f in (desk.get("jp") or {}).get("forecast") or [] if place in (f.get("location") or "")]    # "与那国島付近" = 0 km
    return min(pts)[1] if pts else ""


def desk_value(*keys: str):
    src = os.environ.get("THUMB_DESK") or stream_page() + "live/desk.json"
    try:
        d = json.load(urllib.request.urlopen(src, timeout=15)) if src.startswith("http") else json.loads(Path(src).read_text(encoding="utf-8"))
        for k in keys:
            d = d[k]
        return d
    except (OSError, ValueError, KeyError, TypeError):
        return None


def tw_text(over: dict | None = None) -> dict:
    """The tw style's words (l1, l2, l3, chip, chipLab, stamp, arrow): THUMB_TW_TEXT's JSON file, then any overrides.
    The operator writes them from official sources; a refresh only changes the time stamp and the satellite frame."""
    text = json.loads(TW_TEXT.read_text(encoding="utf-8")) if TW_TEXT.is_file() else {}
    text.update({k: v for k, v in (over or {}).items() if v is not None})
    if text.get("cdJma"):
        text["cdTime"] = jma_point_time(text["cdJma"])
    if text.get("cdLandfall"):                   # India: count down to IMD's landfall time (desk.json in.imd.landfall.timeUTC)
        text["cdTime"] = desk_value("in", "imd", "landfall", "timeUTC") or ""
    if not text.get("l2"):
        raise RuntimeError(f"the tw thumbnail needs its words: write l1/l2 (and optionally l3, chip) to {TW_TEXT} or pass --l1/--l2")
    return text


def render(lang: str = "", out: Path | None = None, timeout: float = 120, style: str | None = None,
           text: dict | None = None) -> tuple[Path, dict]:
    """Render and save the thumbnail; returns (path, the page's summary: sat time, desk time, text)."""
    out = Path(out or REPO / "output" / "youtube" / f"thumb_{lang or 'en'}.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    style = style or os.environ.get("THUMB_STYLE", "hero")
    if style == "tw":
        words = tw_text(text)                       # fail before fetching anything when the words are missing
        if not tw_ready(frame="india" if words.get("frame") == "in" else "tw"):
            raise RuntimeError("Taiwan satellite frame unavailable")
        page = "thumb-in.html" if words.get("tpl") == "in" else "thumb-tw.html"     # tpl=in: the Indian news-style template
        url = stream_page() + page + "?" + urllib.parse.urlencode({k: str(v) for k, v in words.items() if v not in (None, "") and k != "tpl"})
    elif style == "hero" and hero_ready():
        url = stream_page() + "thumb-hero.html" + (f"?lang={lang}" if lang else "")
    else:
        url = stream_page() + "?thumb=1&live=0" + (f"&lang={lang}" if lang else "")
    log = open(REPO / ".run" / "encoder" / "thumbnail_chromium.log", "a")
    proc = subprocess.Popen([UDOCKER, "run", "--nobanner", "-v", "/tmp:/tmp", "yt-encoder", "chromium", "--headless=new", "--no-sandbox",
                             "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", f"--user-data-dir=/tmp/thumb-profile-{CDP_PORT}",
                             f"--remote-debugging-port={CDP_PORT}", "--remote-debugging-address=127.0.0.1", "about:blank"],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        ws_url, t0 = None, time.time()
        while ws_url is None and time.time() - t0 < 60:
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=3))
                ws_url = next((t["webSocketDebuggerUrl"] for t in targets if t.get("type") == "page"), None)
            except OSError:
                pass
            if ws_url is None:
                if proc.poll() is not None:
                    raise RuntimeError(f"headless chromium exited (rc {proc.returncode}); see .run/encoder/thumbnail_chromium.log")
                time.sleep(1)
        if ws_url is None:
            raise TimeoutError("headless chromium did not open its DevTools port")
        info = asyncio.run(_capture(ws_url, url, out, timeout))
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    out.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", default="", help="language (ja, zh, tl; empty = English); the map style has no zh")
    ap.add_argument("--style", default=None, choices=["hero", "map", "tw"], help="default: THUMB_STYLE or hero; tw = Taiwan news style")
    ap.add_argument("--out", default=None)
    tw = ap.add_argument_group("tw style words (override THUMB_TW_TEXT's file; {..} marks the accent colour)")
    for k, h in (("l1", "yellow line"), ("l2", "white line, biggest"), ("l3", "small boxed line"), ("chip", "right chip rows, split by |"),
                 ("chipLab", "chip label (default 中央氣象署)"), ("stamp", "LIVE time stamp (default: now, Taiwan time)"),
                 ("arrow", "km of forecast track drawn from the eye (default 300; 0 = none)")):
        tw.add_argument(f"--{k}", default=None, help=h)
    tw.add_argument("--desk", default=None, help="desk.json path or URL for the tw frame (default: THUMB_DESK or the stream's live/desk.json)")
    a = ap.parse_args()
    if a.desk:
        os.environ["THUMB_DESK"] = a.desk
    words = {k: getattr(a, k) for k in ("l1", "l2", "l3", "chip", "chipLab", "stamp", "arrow")}
    path, info = render(a.lang, Path(a.out) if a.out else None, style=a.style, text=words)
    print(f"{path} ({path.stat().st_size / 1024:.0f} KB): {json.dumps(info['text'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

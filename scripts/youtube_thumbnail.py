"""Render the YouTube thumbnail from live data: the stream page in thumbnail mode (html/champi-desk.html ?thumb=1).

    /home/andyshi2/.conda/envs/ai-livestream/bin/python scripts/youtube_thumbnail.py --lang ja [--out output/youtube/thumb_ja.jpg]

The page draws the newest Himawari infrared frame, the official track and cone, and a headline built from the
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
import os
import signal
import subprocess
import sys
import time
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


def render(lang: str = "", out: Path | None = None, timeout: float = 120) -> tuple[Path, dict]:
    """Render and save the thumbnail; returns (path, the page's summary: sat time, desk time, text)."""
    out = Path(out or REPO / "output" / "youtube" / f"thumb_{lang or 'en'}.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    url = stream_page() + "?thumb=1&live=0" + (f"&lang={lang}" if lang else "")
    log = open(REPO / ".run" / "encoder" / "thumbnail_chromium.log", "a")
    proc = subprocess.Popen([UDOCKER, "run", "--nobanner", "-v", "/tmp:/tmp", "yt-encoder", "chromium", "--headless=new", "--no-sandbox",
                             "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", "--user-data-dir=/tmp/thumb-profile",
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
    ap.add_argument("--lang", default="", help="page language (ja, tl; empty = English)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    path, info = render(a.lang, Path(a.out) if a.out else None)
    print(f"{path} ({path.stat().st_size / 1024:.0f} KB): {json.dumps(info['text'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Hourly thumbnail refresh for a broadcast whose launcher cannot upload (stale API connection), with a fresh client each time.

    THUMB_STYLE=tw EC2_STREAM_ID=taiwan python scripts/thumb_sidecar.py --video IF6p5quZ_CY --lang zh --minute 26 --hours 11
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import youtube_thumbnail  # noqa: E402
from broadcast import youtube  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--minute", type=int, default=26, help="minute past each hour to refresh")
    ap.add_argument("--hours", type=float, default=12)
    a = ap.parse_args()
    end = time.time() + a.hours * 3600
    while time.time() < end:
        now = datetime.now(timezone.utc)
        nxt = now.replace(minute=a.minute, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(hours=1)
        time.sleep((nxt - now).total_seconds())
        try:
            path, info = youtube_thumbnail.render(a.lang, out=REPO / "output" / "youtube" / f"thumb_{a.lang}_sidecar.jpg")
            youtube.set_thumbnail(a.video, path, youtube.service())
            print(f"{datetime.now(timezone.utc):%H:%M} thumbnail set: {info['text'].get('l1')}", flush=True)
        except Exception as error:  # noqa: BLE001 - try again next hour
            print(f"{datetime.now(timezone.utc):%H:%M} refresh failed: {error}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

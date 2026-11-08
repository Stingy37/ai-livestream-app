"""Election-night operator watch: blocks until something needs the operator, then prints it and exits.

    python scripts/election_watch.py [--max-min 25] [--live es,ja,zh]

Exits (0) with one line per event when:
  CALLS     call_candidates.json has a candidate for a race that calls.json doesn't have yet (review + confirm)
  STALE     a stream's current.json is older than --stale-min while the runner should be refreshing it
  RUNNER    a runner process is down
  ENCODER   a stream listed in --live has no ffmpeg encoder process
  FEED      a feed (TX/OH/AK) reported an error other than the expected blocks
  HEARTBEAT nothing happened for --max-min minutes (so the operator still looks in regularly)
Seen candidates are remembered in .run/election/watch_seen.json so the same story is reported once.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "output" / "election"
SEEN = REPO / ".run" / "election" / "watch_seen.json"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _pgrep(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def check(args, seen: set[str]) -> list[str]:
    ev = []
    cands = _load(OUT / "call_candidates.json", {})
    calls = (_load(OUT / "calls.json", {}) or {}).get("calls", {})
    items = cands.get("candidates") or cands.get("items") or []
    if isinstance(items, dict):
        items = [dict(v, state=k) if isinstance(v, dict) else {"state": k, "list": v} for k, v in items.items()]
    for c in items:
        if not isinstance(c, dict):
            continue
        lst = c.get("list") if "list" in c else [c]
        for x in lst if isinstance(lst, list) else [lst]:
            st = x.get("state") or c.get("state")
            tag = f"{st}|{x.get('key')}|{x.get('url')}"
            if tag in seen or (st in calls and not calls[st].get("retracted")):
                continue
            seen.add(tag)
            ev.append(f"CALLS {st} {x.get('key')} | {x.get('headline') or x.get('title')} | {x.get('url')} | {x.get('published') or x.get('published_at') or ''}")
    now = time.time()
    for lang in ("es", "ja", "zh"):
        s = f"election-{lang}"
        if not _pgrep(f"python -m election.run --lang {lang} --stream {s}"):
            ev.append(f"RUNNER {s} down")
        cur = OUT / "air" / s / "current.json"
        if cur.exists() and now - cur.stat().st_mtime > args.stale_min * 60:
            ev.append(f"STALE {s} current.json {int((now - cur.stat().st_mtime) / 60)} min old")
    for lang in [x for x in args.live.split(",") if x]:
        if not _pgrep(f"election-{lang}") or not _pgrep("ffmpeg"):
            ev.append(f"ENCODER election-{lang}: no encoder process")
    log = REPO / ".run" / "election" / "feeds.log"
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        for line in tail:
            if line[:3] in ("TX:", "OH:", "AK:") and ("ParseError" in line or "Traceback" in line):
                tag = "FEED|" + line[:160]
                if tag not in seen:
                    seen.add(tag)
                    ev.append("FEED " + line[:200])
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-min", type=float, default=25)
    ap.add_argument("--stale-min", type=float, default=20)
    ap.add_argument("--live", default="")
    ap.add_argument("--interval", type=float, default=30)
    args = ap.parse_args()
    seen = set(_load(SEEN, []))
    t0 = time.time()
    while True:
        ev = check(args, seen)
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen)), encoding="utf-8")
        if ev:
            print(datetime.now(timezone.utc).strftime("%H:%M:%SZ"), *ev, sep="\n")
            return 0
        if time.time() - t0 > args.max_min * 60:
            print(datetime.now(timezone.utc).strftime("%H:%M:%SZ"), "HEARTBEAT nothing new")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

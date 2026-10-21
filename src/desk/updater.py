"""Build desk.json and publish it to EC2, once or on a timer.

    python -m desk.updater                 # one update, published
    python -m desk.updater --no-publish    # one update, written to output/desk/desk.json only
    python -m desk.updater --loop          # every DESK_INTERVAL_S seconds until Ctrl+C

main.py runs a ``DeskUpdater`` thread next to the broadcast loop (DESK_ENABLED=1).

Environment: DESK_INTERVAL_S (600), DESK_DIR (output/desk), DESK_STORM (default: config storm.name),
DESK_JMA_TC / DESK_JTWC_ID (fallback ids when discovery fails), DESK_LLM (1: build the text sections
with the Lumen pool), DESK_KEEP_HISTORY (48 local copies), CONFIG_PATH, RUN_ROOT.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from desk.build import SECTIONS, build_desk, validate  # noqa: E402

log = logging.getLogger("desk")

DESK_DIR = Path(os.environ.get("DESK_DIR", REPO / "output" / "desk"))
INTERVAL_S = float(os.environ.get("DESK_INTERVAL_S", "600"))
KEEP_HISTORY = int(os.environ.get("DESK_KEEP_HISTORY", "48"))


def storm_hint() -> str:
    if os.environ.get("DESK_STORM"):
        return os.environ["DESK_STORM"]
    cfg = Path(os.environ.get("CONFIG_PATH", REPO / "saved_configs" / "example.json"))
    try:
        return json.loads(cfg.read_text(encoding="utf-8")).get("config", {}).get("storm", {}).get("name", "")
    except (OSError, ValueError):
        return ""


def _ask():
    if os.environ.get("DESK_LLM", "1") != "1":
        return None
    from models import lumen

    def ask(system: str, user: str) -> str:
        return lumen.ask(system, user, temperature=0.1, max_tokens=1800)
    return ask


def load_previous() -> dict | None:
    p = DESK_DIR / "desk.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(doc: dict) -> Path:
    DESK_DIR.mkdir(parents=True, exist_ok=True)
    (DESK_DIR / "history").mkdir(exist_ok=True)
    p = DESK_DIR / "desk.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (DESK_DIR / "history" / f"desk-{stamp}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    for old in sorted((DESK_DIR / "history").glob("desk-*.json"))[:-KEEP_HISTORY]:
        old.unlink(missing_ok=True)
    return p


def summarize(doc: dict) -> dict:
    prov = doc.get("provenance") or {}
    out = {}
    for s in SECTIONS:
        v = doc.get(s)
        n = (len(v.get("points", [])) if isinstance(v, dict) and "points" in v else
             len(v.get("items", [])) if isinstance(v, dict) and "items" in v else
             sum(len(x["members"]) for x in v.get("sets", [])) if isinstance(v, dict) and "sets" in v else
             len(v) if isinstance(v, (list, dict)) else (1 if v else 0))
        out[s] = {"ok": bool((prov.get(s) or {}).get("ok")), "stale": s in (doc.get("stale") or []), "count": n,
                  "source": (prov.get(s) or {}).get("source", ""), "error": (prov.get(s) or {}).get("error")}
    return out


def run_once(publish: bool = True, publisher=None) -> dict:
    """One update. Returns {"ok", "published", "fresh", "stale", "problems", "path", ...}."""
    prev = load_previous()
    run_root = Path(os.environ.get("RUN_ROOT", REPO / "output" / "runs"))
    t0 = time.time()
    doc, report = build_desk(prev, storm_hint=storm_hint(), ask=_ask(), run_root=run_root,
                             fallback_jma=os.environ.get("DESK_JMA_TC", "TC2636"),
                             fallback_jtwc=os.environ.get("DESK_JTWC_ID", "wp2926"))
    problems = validate(doc)
    result = {"ok": not problems, "published": False, "fresh": report["fresh"], "stale": report["stale"],
              "missing": report["missing"], "problems": problems, "llm_calls": report["llm_calls"],
              "dropped_text_items": len(report["dropped_text_items"]), "seconds": round(time.time() - t0, 1)}
    if problems:
        log.error("desk.json NOT updated (invalid): %s", problems[:6])
        return result
    prev_fresh = sum(1 for v in ((prev or {}).get("provenance") or {}).values() if v.get("ok"))
    if prev and len(report["fresh"]) < prev_fresh:
        log.warning("desk.json has fewer fresh sections than the last one (%d < %d); stale: %s",
                    len(report["fresh"]), prev_fresh, report["stale"])
    (DESK_DIR / "last_report.json").parent.mkdir(parents=True, exist_ok=True)
    (DESK_DIR / "last_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    result["path"] = str(_write(doc))
    if publish:
        try:
            if publisher is None:
                from broadcast.publisher import Publisher

                publisher = Publisher()
            reply = publisher.push_desk(doc)
            result["published"] = True
            result["reply"] = {k: reply.get(k) for k in ("ok", "generated_at", "bytes")}
        except Exception as e:  # noqa: BLE001
            result["publish_error"] = str(e)[:300]
            log.error("desk.json publish failed: %s", e)
    log.info("desk update: fresh=%s stale=%s llm_calls=%d dropped=%d published=%s (%.0fs)",
             ",".join(report["fresh"]) or "-", ",".join(report["stale"]) or "-", report["llm_calls"],
             len(report["dropped_text_items"]), result["published"], result["seconds"])
    return result


class DeskUpdater(threading.Thread):
    """Background thread: run_once() now, then every ``interval`` seconds, until stop()."""

    def __init__(self, interval: float = INTERVAL_S, publish: bool = True) -> None:
        super().__init__(name="desk-updater", daemon=True)
        self.interval = max(60.0, float(interval))
        self.publish = publish
        self._stop = threading.Event()
        self.last: dict | None = None
        self._publisher = None

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.publish and self._publisher is None:
                    from broadcast.publisher import Publisher

                    self._publisher = Publisher()
                self.last = run_once(publish=self.publish, publisher=self._publisher)
            except Exception:  # noqa: BLE001 - the updater must never take the broadcast down
                log.exception("desk update crashed; retrying next interval")
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--loop", action="store_true", help=f"update every DESK_INTERVAL_S ({INTERVAL_S:.0f}) seconds")
    ap.add_argument("--no-publish", action="store_true", help="write output/desk/desk.json only")
    ap.add_argument("--interval", type=float, default=INTERVAL_S)
    a = ap.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(asctime)s  %(levelname)-7s  %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if not a.loop:
        r = run_once(publish=not a.no_publish)
        print(json.dumps(r, indent=1, default=str))
        return 0 if r["ok"] else 1
    t = DeskUpdater(interval=a.interval, publish=not a.no_publish)
    t.start()
    try:
        while t.is_alive():
            t.join(1.0)
    except KeyboardInterrupt:
        t.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

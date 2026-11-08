"""Official election-night results adapters for the six featured 2026 U.S. Senate races.

Each adapter exposes ``fetch(session) -> dict`` returning the "Live results" schema of docs/ELECTION.md, built only
from the state's own official publication (never AP, DDHQ, networks or newspapers). See research/election/feeds.md.

CLI (run from src/, like the other desk tools):

    python -m election.feeds TX --out output/election/live/
    python -m election.feeds ALL --out output/election/live/ --loop 180

Relative ``--out`` paths are resolved against the repository root, so the files land in
<repo>/output/election/live/<ST>.json (written atomically). A failed fetch never overwrites the last good file.
"""

from __future__ import annotations

import argparse
import inspect
import logging
import sys
import time
from pathlib import Path

from . import ak, common, ks, me, mi, oh, tx

ADAPTERS = {
    "TX": tx.fetch,
    "AK": ak.fetch,
    "KS": ks.fetch,
    "ME": me.fetch,
    "OH": oh.fetch,
    "MI": mi.fetch,
}

log = logging.getLogger("election.feeds")


def run_once(states: list[str], out: Path, *, allow_test: bool = False, session=None) -> dict[str, str]:
    """Fetch each state and write <out>/<ST>.json atomically. Returns {state: "ok" | "<ErrorType>: message"}."""
    session = session or common.make_session()
    status: dict[str, str] = {}
    for st in states:
        fn = ADAPTERS[st]
        kwargs = {"allow_test": True} if allow_test and "allow_test" in inspect.signature(fn).parameters else {}
        try:
            res = fn(session, **kwargs)
            common.write_json_atomic(out / f"{st}.json", res)
            status[st] = (f"ok  total_votes={res['total_votes']:,} precincts={res['precincts']} "
                          f"units={len(res['units'])} updated={res['source_updated_at']}")
        except common.FeedError as e:
            status[st] = f"{type(e).__name__}: {e}"
        except Exception as e:                       # an adapter bug must not stop the other states
            log.exception("%s adapter crashed", st)
            status[st] = f"{type(e).__name__}: {e}"
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m election.feeds", description=__doc__.split("\n\n")[0])
    ap.add_argument("states", nargs="+", help="state codes (TX AK KS ME OH MI) or ALL")
    ap.add_argument("--out", default="output/election/live/", help="output directory (relative = repo root)")
    ap.add_argument("--loop", type=float, default=0, help="repeat every N seconds (min 60) until Ctrl+C")
    ap.add_argument("--allow-test", action="store_true", help="accept files the source flags as test data")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(message)s")
    states = list(ADAPTERS) if [s.upper() for s in a.states] == ["ALL"] else [s.upper() for s in a.states]
    bad = [s for s in states if s not in ADAPTERS]
    if bad:
        ap.error(f"unknown state(s) {bad}; choose from {sorted(ADAPTERS)} or ALL")
    out = Path(a.out)
    if not out.is_absolute():
        out = common.REPO / out
    session = common.make_session()
    # In --loop mode a state whose server answered with a bot challenge / WAF block (SourceBlocked) is asked again
    # only every ELECTION_BLOCKED_RETRY_S (default 900 s), not every cycle: an honest client backs off.
    blocked_retry = max(float(common.env("ELECTION_BLOCKED_RETRY_S", "900")), a.loop)
    next_try: dict[str, float] = {}
    while True:
        due = [st for st in states if next_try.get(st, 0.0) <= time.monotonic()]
        if a.loop > 0:
            print(f"--- {common.utcnow()} cycle: {' '.join(due) or '(none due)'}", flush=True)
        status = run_once(due, out, allow_test=a.allow_test, session=session)
        for st, msg in status.items():
            print(f"{st}: {msg}" + (f"  -> {out / (st + '.json')}" if msg.startswith("ok") else ""), flush=True)
            if a.loop > 0 and msg.startswith("SourceBlocked"):
                next_try[st] = time.monotonic() + blocked_retry
                print(f"{st}: blocked; next try in {blocked_retry:.0f} s", flush=True)
        if a.loop <= 0:
            return 0 if all(m.startswith("ok") for m in status.values()) else 1
        time.sleep(max(a.loop, 60.0))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
# Election night: poll the six official state results feeds into output/election/live/<ST>.json, every 120 s.
#
#   bash scripts/election_feeds.sh            # start in the background (idempotent: a running loop is left alone)
#   bash scripts/election_feeds.sh status     # pid, last cycle, per-state result
#   bash scripts/election_feeds.sh stop       # same as: touch .run/STOP_ELECTION_FEEDS
#   bash scripts/election_feeds.sh run        # foreground (what "start" runs under nohup)
#
# Runs `python -m election.feeds ALL --out output/election/live/ --loop $ELECTION_FEEDS_LOOP_S` from src/, logging to
# .run/election/feeds.log. The loop is never faster than 120 s (one Texas poll is ~6 MB). A source that answers with a
# bot challenge (KS, MI, ME so far) is asked again only every ELECTION_BLOCKED_RETRY_S (900 s). Test data is never
# accepted here (no --allow-test). If Python exits unexpectedly it is restarted after one loop interval.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
RUN_DIR="$REPO_ROOT/.run/election"
LOG="$RUN_DIR/feeds.log"
PID_FILE="$RUN_DIR/feeds.pid"
STOP_FILE="$REPO_ROOT/.run/STOP_ELECTION_FEEDS"
LOOP_S="${ELECTION_FEEDS_LOOP_S:-120}"
(( LOOP_S < 120 )) && LOOP_S=120
export TX_ELECTION_ID="${TX_ELECTION_ID:-53815}"     # 2026 NOVEMBER GENERAL: skips the discovery request every poll
mkdir -p "$RUN_DIR"

running() { [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null \
            && tr '\0' ' ' < "/proc/$(cat "$PID_FILE")/cmdline" 2>/dev/null | grep -q "election_feeds.sh run"; }

case "${1:-start}" in
  start)
    if running; then echo "election feeds already running (pid $(cat "$PID_FILE")); log: $LOG"; exit 0; fi
    rm -f "$STOP_FILE"
    nohup bash "$REPO_ROOT/scripts/election_feeds.sh" run >>"$LOG" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
    sleep 1
    running && echo "election feeds started (pid $(cat "$PID_FILE"), every ${LOOP_S}s); log: $LOG" \
            || { echo "election feeds failed to start; see $LOG" >&2; exit 1; } ;;
  stop)
    touch "$STOP_FILE"
    running && echo "stop requested (pid $(cat "$PID_FILE") exits within ~5 s)" || echo "election feeds not running" ;;
  status)
    if running; then echo "running (pid $(cat "$PID_FILE"))"; else echo "not running"; fi
    awk '/^--- /{block=""} {block=block $0 "\n"} END{printf "%s", block}' "$LOG" 2>/dev/null | cut -c1-200
    running ;;
  run)
    cd "$REPO_ROOT/src"
    echo "=== $(date -u +%FT%TZ) election feeds: loop ${LOOP_S}s, TX_ELECTION_ID=$TX_ELECTION_ID"
    child=""
    trap '[[ -n "$child" ]] && kill "$child" 2>/dev/null; exit 0' TERM INT
    while [[ ! -e "$STOP_FILE" ]]; do
      "$PY" -u -m election.feeds ALL --out output/election/live/ --loop "$LOOP_S" &
      child=$!
      while kill -0 "$child" 2>/dev/null; do
        if [[ -e "$STOP_FILE" ]]; then kill "$child" 2>/dev/null; wait "$child" 2>/dev/null || true; break; fi
        sleep 5
      done
      wait "$child" 2>/dev/null && rc=0 || rc=$?
      [[ -e "$STOP_FILE" ]] && break
      echo "=== $(date -u +%FT%TZ) election.feeds exited (rc $rc); restarting in ${LOOP_S}s"
      for _ in $(seq 1 $(( LOOP_S / 5 ))); do [[ -e "$STOP_FILE" ]] && break; sleep 5; done
    done
    echo "=== $(date -u +%FT%TZ) election feeds stopped (STOP file)"
    rm -f "$PID_FILE" ;;
  *) echo "usage: $0 [start|stop|status|run]" >&2; exit 2 ;;
esac

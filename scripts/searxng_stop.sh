#!/usr/bin/env bash
# Stop the SearXNG instance started by scripts/searxng_start.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEARXNG_RUN_DIR="${SEARXNG_RUN_DIR:-$REPO_ROOT/.run/searxng}"
SEARXNG_STOP_TIMEOUT="${SEARXNG_STOP_TIMEOUT:-15}"
PID_FILE="$SEARXNG_RUN_DIR/searxng.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "no pid file at $PID_FILE; SearXNG is not running (or was not started by searxng_start.sh)"
    exit 0
fi
pid="$(cat "$PID_FILE")"
if ! kill -0 "$pid" 2>/dev/null; then
    echo "SearXNG (pid $pid) is not running; removing stale pid file"
    rm -f "$PID_FILE"
    exit 0
fi
echo "stopping SearXNG (process group $pid)"
kill -TERM -- "-$pid" 2>/dev/null || true
deadline=$((SECONDS + SEARXNG_STOP_TIMEOUT))
while kill -0 -- "-$pid" 2>/dev/null; do
    if (( SECONDS >= deadline )); then
        echo "still running after ${SEARXNG_STOP_TIMEOUT}s; sending SIGKILL"
        kill -KILL -- "-$pid" 2>/dev/null || true
        break
    fi
    sleep 1
done
rm -f "$PID_FILE"
echo "SearXNG stopped"

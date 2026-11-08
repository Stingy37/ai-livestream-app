#!/usr/bin/env bash
# Start a local SearXNG metasearch instance for the agentic web scraper (JSON API on 127.0.0.1:8890; 8888 is JupyterHub on ICRN).
#
# SearXNG runs from its git checkout (SEARXNG_SRC) inside its own venv (SEARXNG_PY); settings come from
# scripts/searxng/settings.yml. Idempotent: exits 0 if an instance started by this script is healthy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SEARXNG_SRC="${SEARXNG_SRC:-/home/andyshi2/searxng}"
SEARXNG_PY="${SEARXNG_PY:-/home/andyshi2/searxng-venv/bin/python}"
SEARXNG_SETTINGS="${SEARXNG_SETTINGS:-$REPO_ROOT/scripts/searxng/settings.yml}"
SEARXNG_HOST="${SEARXNG_HOST:-127.0.0.1}"
SEARXNG_PORT="${SEARXNG_PORT:-8890}"
SEARXNG_STARTUP_TIMEOUT="${SEARXNG_STARTUP_TIMEOUT:-120}"   # seconds
SEARXNG_RUN_DIR="${SEARXNG_RUN_DIR:-$REPO_ROOT/.run/searxng}"

PID_FILE="$SEARXNG_RUN_DIR/searxng.pid"
LOG_FILE="$SEARXNG_RUN_DIR/searxng.log"
HEALTH_URL="http://$SEARXNG_HOST:$SEARXNG_PORT/search?q=test&format=json"

healthy() { curl -sf -m 15 "$HEALTH_URL" 2>/dev/null | grep -q '"results"'; }

if [[ ! -x "$SEARXNG_PY" ]]; then
    echo "SearXNG python not found at $SEARXNG_PY; set SEARXNG_PY" >&2
    exit 1
fi
if [[ ! -f "$SEARXNG_SRC/searx/webapp.py" ]]; then
    echo "SearXNG checkout not found at $SEARXNG_SRC; set SEARXNG_SRC" >&2
    exit 1
fi

mkdir -p "$SEARXNG_RUN_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    if healthy; then
        echo "SearXNG already running (pid $(cat "$PID_FILE")) on port $SEARXNG_PORT"
        exit 0
    fi
    echo "SearXNG pid $(cat "$PID_FILE") alive but not healthy yet; waiting for it"
else
    rm -f "$PID_FILE"
    if healthy; then
        echo "something is already serving SearXNG on $SEARXNG_HOST:$SEARXNG_PORT (not started by this script)"
        exit 0
    fi
    echo "starting SearXNG from $SEARXNG_SRC on $SEARXNG_HOST:$SEARXNG_PORT"
    cd "$SEARXNG_SRC"
    # setsid: own process group so searxng_stop.sh can take the whole thing down.
    SEARXNG_SETTINGS_PATH="$SEARXNG_SETTINGS" \
    SEARXNG_PORT="$SEARXNG_PORT" SEARXNG_BIND_ADDRESS="$SEARXNG_HOST" \
    SEARXNG_SECRET="${SEARXNG_SECRET:-$(openssl rand -hex 24)}" \
    PYTHONPATH="$SEARXNG_SRC" \
    setsid "$SEARXNG_PY" -m searx.webapp >"$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
fi

echo "waiting for SearXNG (log: $LOG_FILE)"
deadline=$((SECONDS + SEARXNG_STARTUP_TIMEOUT))
until healthy; do
    if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "SearXNG exited during startup; last log lines:" >&2
        tail -n 30 "$LOG_FILE" >&2
        rm -f "$PID_FILE"
        exit 1
    fi
    if (( SECONDS >= deadline )); then
        echo "SearXNG not healthy after ${SEARXNG_STARTUP_TIMEOUT}s; stopping it. Last log lines:" >&2
        tail -n 30 "$LOG_FILE" >&2
        "$REPO_ROOT/scripts/searxng_stop.sh"
        exit 1
    fi
    sleep 2
done

echo "SearXNG ready: http://$SEARXNG_HOST:$SEARXNG_PORT/search?q=...&format=json (pid $(cat "$PID_FILE"))"

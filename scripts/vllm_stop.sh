#!/usr/bin/env bash
# Stop the vLLM server started by scripts/vllm_start.sh and free its GPU memory.
#
# Sends SIGTERM to the server's whole process group (API server + engine
# workers), waits up to VLLM_STOP_TIMEOUT seconds, then SIGKILLs anything left.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VLLM_RUN_DIR="$REPO_ROOT/.run/vllm"
VLLM_STOP_TIMEOUT="30"                    # seconds
PID_FILE="$VLLM_RUN_DIR/vllm.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "no pid file at $PID_FILE; vLLM is not running (or was not started by vllm_start.sh)"
    exit 0
fi

pid="$(cat "$PID_FILE")"
if ! kill -0 "$pid" 2>/dev/null; then
    echo "vLLM (pid $pid) is not running; removing stale pid file"
    rm -f "$PID_FILE"
    exit 0
fi

# vllm_start.sh launched the server with setsid, so its pid is also its process group id.
echo "stopping vLLM (process group $pid)"
kill -TERM -- "-$pid" 2>/dev/null || true

deadline=$((SECONDS + VLLM_STOP_TIMEOUT))
while kill -0 -- "-$pid" 2>/dev/null; do
    if (( SECONDS >= deadline )); then
        echo "still running after ${VLLM_STOP_TIMEOUT}s; sending SIGKILL"
        kill -KILL -- "-$pid" 2>/dev/null || true
        break
    fi
    sleep 1
done

rm -f "$PID_FILE"
echo "vLLM stopped"

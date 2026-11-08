#!/usr/bin/env bash
# Stop the MOSS-TTS server started by moss_tts_start.sh and free its GPU memory.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$REPO_ROOT/.run/moss/moss.pid"
[[ -f "$PID_FILE" ]] || { echo "MOSS TTS is not running"; exit 0; }
pid="$(cat "$PID_FILE")"
kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
kill -KILL -- "-$pid" 2>/dev/null || true
rm -f "$PID_FILE"; echo "MOSS TTS stopped"

#!/usr/bin/env bash
# Start the MOSS-TTS v1.5 server (multilingual TTS, used for Tagalog) on 127.0.0.1:${MOSS_PORT}.
# Idempotent like vllm_start.sh. Runs in its own conda env because MOSS pins torch 2.9.1 / Transformers 5.0.
#   MOSS_MODEL_PATH  full MOSS-TTS-v1.5 (default: 24.8 GB GPU, 24 kHz; vLLM must sleep while it is loaded,
#                    which the harness does, see src/models/gpu.py) or MOSS-TTS-Local-Transformer-v1.5 (12.8 GB)
#   The server starts empty (MOSS_PRELOAD=0) and loads the model on /load or on the first /synthesize.
#   MOSS_CODEC_PATH  MOSS-Audio-Tokenizer-v2 for Local-Transformer, MOSS-Audio-Tokenizer for the full model
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOSS_PY="${MOSS_PY:-/home/andyshi2/.conda/envs/moss-tts/bin/python}"
export MOSS_MODEL_PATH="${MOSS_MODEL_PATH:-/home/andyshi2/pre-models/MOSS-TTS-v1.5}"
export MOSS_CODEC_PATH="${MOSS_CODEC_PATH:-/home/andyshi2/pre-models/MOSS-Audio-Tokenizer}"
export MOSS_HOST="${MOSS_HOST:-127.0.0.1}"
export MOSS_PORT="${MOSS_PORT:-8010}"
export MOSS_VOICE_DIR="${MOSS_VOICE_DIR:-$REPO_ROOT/model_weights/moss_voices}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
# torchcodec (reference-voice loading) needs FFmpeg from the env and NVIDIA NPP from pip
MOSS_ENV="$(dirname "$(dirname "$MOSS_PY")")"
export LD_LIBRARY_PATH="$MOSS_ENV/lib/python3.12/site-packages/nvidia/npp/lib:$MOSS_ENV/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
MOSS_STARTUP_TIMEOUT="${MOSS_STARTUP_TIMEOUT:-900}"
RUN_DIR="$REPO_ROOT/.run/moss"; PID_FILE="$RUN_DIR/moss.pid"; LOG_FILE="$RUN_DIR/moss.log"
mkdir -p "$RUN_DIR"
health() { curl -sf "http://$MOSS_HOST:$MOSS_PORT/health" >/dev/null 2>&1; }
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null && health; then
    echo "MOSS TTS already running (pid $(cat "$PID_FILE")) on port $MOSS_PORT"; exit 0
fi
if ! [[ -f "$PID_FILE" ]] || ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "starting MOSS TTS: $MOSS_MODEL_PATH on $MOSS_HOST:$MOSS_PORT"
    PYTHONPATH="$REPO_ROOT/src" setsid "$MOSS_PY" -m tts_server.moss_server >"$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
fi
deadline=$((SECONDS + MOSS_STARTUP_TIMEOUT))
until health; do
    if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "MOSS exited during startup:" >&2; tail -n 30 "$LOG_FILE" >&2; rm -f "$PID_FILE"; exit 1; fi
    (( SECONDS >= deadline )) && { echo "MOSS not ready after ${MOSS_STARTUP_TIMEOUT}s" >&2; tail -n 30 "$LOG_FILE" >&2; exit 1; }
    sleep 3
done
echo "MOSS TTS ready: http://$MOSS_HOST:$MOSS_PORT (pid $(cat "$PID_FILE"))"

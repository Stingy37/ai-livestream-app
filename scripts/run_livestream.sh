#!/usr/bin/env bash
# Run the whole Typhoon Champi pipeline on this ICRN machine for hours, unattended.
#
#   bash scripts/run_livestream.sh                 # generate, publish, keep the on-air loop running
#   MODE=generate bash scripts/run_livestream.sh   # stages 1-4 + one publish, then exit
#   DRY_RUN=1 bash scripts/run_livestream.sh       # no publishing, fast on-air clock
#
# Every argument of the entrypoint (besides what the json config defines) is an environment
# variable below; export any of them before calling this script to override. The script:
#   1. starts the local services if they are not up (vLLM with the LoRA, SearXNG),
#   2. keeps the ICRN JupyterHub server alive (icrn-keepalive, if installed),
#   3. runs src/main.py and restarts it with back-off if it crashes, resuming the same RUN_ID,
#      until MAX_HOURS have passed or .run/STOP exists.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- run ---------------------------------------------------------------------------------
export CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/saved_configs/example.json}"
export RUN_ROOT="${RUN_ROOT:-$REPO_ROOT/output/runs}"
export RUN_ID="${RUN_ID:-run-$(date -u +%Y%m%dT%H%M%SZ)}"
export RESUME="${RESUME:-1}"                 # reuse stage artifacts of the same RUN_ID after a crash
export MODE="${MODE:-full}"                  # full | generate | broadcast
export MAX_HOURS="${MAX_HOURS:-6}"           # the on-air loop stops cleanly after this
export MAX_WORKERS="${MAX_WORKERS:-4}"       # scene processes per stage
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export PUBLISH="${PUBLISH:-1}"               # upload packages to S3 through the EC2 endpoint
export KEEP_PACKAGES="${KEEP_PACKAGES:-3}"
export DRY_RUN="${DRY_RUN:-0}"
export SCENES="${SCENES:-}"                  # comma-separated node keys to restrict to (debugging)
export RESTART_LIMIT="${RESTART_LIMIT:-20}"  # crashes tolerated before giving up
export START_SERVICES="${START_SERVICES:-1}" # start vLLM + SearXNG if they are not running
export ICRN_KEEPALIVE="${ICRN_KEEPALIVE:-1}"

# ---- Lumen (UIUC) API key pool: comma/whitespace separated, or one per line in LUMEN_KEYS_FILE --
export LUMEN_API_KEYS="${LUMEN_API_KEYS:-}"
export LUMEN_KEYS_FILE="${LUMEN_KEYS_FILE:-$REPO_ROOT/secrets/lumen_keys.txt}"
export LUMEN_BASE_URL="${LUMEN_BASE_URL:-https://lumen.computes.illinois.edu/v1}"
export LUMEN_MODEL="${LUMEN_MODEL:-deepseek-v4-flash}"
export LUMEN_TIMEOUT="${LUMEN_TIMEOUT:-120}"
export LUMEN_MAX_ATTEMPTS="${LUMEN_MAX_ATTEMPTS:-12}"
export LUMEN_LOCAL_FALLBACK="${LUMEN_LOCAL_FALLBACK:-1}"   # answer with local Qwen3 if every key is down

# ---- local vLLM (Qwen3-8B fp8 + dynamic-RAG LoRA; scripts/vllm_start.sh) -------------------
export LOCAL_LLM_URL="${LOCAL_LLM_URL:-http://127.0.0.1:8000/v1}"
export LOCAL_LLM_MODEL="${LOCAL_LLM_MODEL:-qwen3-8b}"
export LOCAL_LLM_MODEL_PATH="${LOCAL_LLM_MODEL_PATH:-/home/andyshi2/pre-models/Qwen3-8B}"
export LORA_NAME="${LORA_NAME:-dynrag}"
export LORA_PATH="${LORA_PATH:-$REPO_ROOT/model_weights/dynrag_lora_v5_step60}"
export LOCAL_LLM_MAX_MODEL_LEN="${LOCAL_LLM_MAX_MODEL_LEN:-9216}"
# vLLM's share of the 35 GB MIG slice. With GPU_TIMESHARE=1 the full MOSS-TTS model gets the whole slice
# while vLLM sleeps during MOSS audio stages, so vLLM keeps its normal share.
export VLLM_GPU_MEM_UTIL="${VLLM_GPU_MEM_UTIL:-0.62}"
export MAX_TOKENS="${MAX_TOKENS:-8192}"          # think (generated + inserted) + answer budget
export THINK_FRACTION="${THINK_FRACTION:-0.75}"
export MAX_OBS_TOKENS="${MAX_OBS_TOKENS:-1024}"
export CONTEXT_TOPK="${CONTEXT_TOPK:-5}"
export GEN_TEMPERATURE="${GEN_TEMPERATURE:-0.6}"
export GEN_TOP_P="${GEN_TOP_P:-0.95}"
export GEN_TOP_K="${GEN_TOP_K:-20}"

# ---- web scraper -----------------------------------------------------------------------------
export SEARXNG_URL="${SEARXNG_URL:-http://127.0.0.1:8890}"   # 8888 is JupyterHub on ICRN
export SCRAPE_MAX_THREADS="${SCRAPE_MAX_THREADS:-8}"
export SCRAPE_TIMEOUT="${SCRAPE_TIMEOUT:-25}"
export SCRAPE_MAX_PAGES="${SCRAPE_MAX_PAGES:-14}"
export REACT_MAX_ROUNDS="${REACT_MAX_ROUNDS:-3}"          # search -> verify -> experts rounds per scene
export STALE_HOURS="${STALE_HOURS:-6}"                      # verify node flags data older than this
export SCRAPE_CACHE_DIR="${SCRAPE_CACHE_DIR:-$REPO_ROOT/output/cache/pages}"
export SCRAPE_CACHE_TTL_S="${SCRAPE_CACHE_TTL_S:-900}"      # a page fetched within this many seconds is reused across scenes
export SCRAPE_MAX_PER_HOST="${SCRAPE_MAX_PER_HOST:-5}"
export SCRAPE_MAX_QUERIES="${SCRAPE_MAX_QUERIES:-3}"        # search queries per ReAct round
export SCRAPE_SEARCH_RESULTS="${SCRAPE_SEARCH_RESULTS:-8}"  # SearXNG hits considered per query
export SCRAPE_FETCH_PER_QUERY="${SCRAPE_FETCH_PER_QUERY:-4}"
export SCRAPE_LLM_DOC_CHARS="${SCRAPE_LLM_DOC_CHARS:-6000}" # text per document shown to the verify/sufficiency prompts (main_text stays complete)
export SCRAPE_BASELINE_MIN_COVERAGE="${SCRAPE_BASELINE_MIN_COVERAGE:-1.0}"   # share of the checklist that must be covered to skip the experts
export SCRAPE_BASELINE_MAX_CONFLICTS="${SCRAPE_BASELINE_MAX_CONFLICTS:-0}"

# ---- QC ----------------------------------------------------------------------------------------
export QC_MAX_REMOVED_FRACTION="${QC_MAX_REMOVED_FRACTION:-0.15}"
export QC_BASE_THRESHOLD="${QC_BASE_THRESHOLD:-0.6}"
export NLI_MODEL_DIR="${NLI_MODEL_DIR:-/home/andyshi2/pre-models/nli-roberta-base}"
export NLI_DEVICE="${NLI_DEVICE:-cpu}"
export SCRIPT_MAX_ATTEMPTS="${SCRIPT_MAX_ATTEMPTS:-3}"
export SCRIPT_SCORE_THRESHOLD="${SCRIPT_SCORE_THRESHOLD:-0}"

# ---- last-stage rewriter (writer/rewriter.py): narrative + analysis pass over every QC-checked script --
export REWRITE_ENABLED="${REWRITE_ENABLED:-1}"
export REWRITE_MODEL="${REWRITE_MODEL:-deepseek-v4-flash}"   # Lumen model; never falls back to the local model
export REWRITE_MAX_ATTEMPTS="${REWRITE_MAX_ATTEMPTS:-2}"     # rewrites tried before keeping the QC-checked draft
export REWRITE_TEMPERATURE="${REWRITE_TEMPERATURE:-0.7}"
export REWRITE_MIN_RATIO="${REWRITE_MIN_RATIO:-0.7}"         # allowed rewrite length, as a share of the draft's words
export REWRITE_MAX_RATIO="${REWRITE_MAX_RATIO:-1.6}"
export REWRITE_QC="${REWRITE_QC:-1}"
export SPEECH_WPS="${SPEECH_WPS:-1.85}"                     # Kokoro words per second; turns style-rule durations into word budgets                         # re-run QC Part B on the rewrite (must not be worse)

# ---- RAG ---------------------------------------------------------------------------------------
export E5_DIR="${E5_DIR:-/home/andyshi2/datasets/models/e5-base-v2}"
export E5_DEVICE="${E5_DEVICE:-cuda}"
export RETRIEVAL_TOP_K="${RETRIEVAL_TOP_K:-5}"
export MIN_SENTENCE_CHARS="${MIN_SENTENCE_CHARS:-25}"

# ---- TTS ---------------------------------------------------------------------------------------
export KOKORO_DIR="${KOKORO_DIR:-/home/andyshi2/pre-models/Kokoro-82M}"
export TTS_DEVICE="${TTS_DEVICE:-cuda}"
export TTS_DEFAULT_VOICE="${TTS_DEFAULT_VOICE:-af_heart}"
export MOSS_URL="${MOSS_URL:-http://127.0.0.1:8010}"                 # MOSS-TTS v1.5 server (scripts/moss_tts_start.sh)
export MOSS_MODEL_PATH="${MOSS_MODEL_PATH:-/home/andyshi2/pre-models/MOSS-TTS-v1.5}"            # full 8B model (24.8 GB GPU)
export MOSS_CODEC_PATH="${MOSS_CODEC_PATH:-/home/andyshi2/pre-models/MOSS-Audio-Tokenizer}"       # its 24 kHz codec
export GPU_TIMESHARE="${GPU_TIMESHARE:-1}"     # sleep vLLM and load MOSS for MOSS audio stages (one stream at a time)
export VLLM_SLEEP_MODE="${VLLM_SLEEP_MODE:-1}" # start vLLM with sleep mode so it can be put to sleep

# ---- EC2 / S3 ----------------------------------------------------------------------------------
export EC2_API_URL="${EC2_API_URL:-https://54.221.147.143:8443}"
export EC2_API_TOKEN_FILE="${EC2_API_TOKEN_FILE:-$REPO_ROOT/secrets/ec2_api_token}"
export EC2_CA_CERT="${EC2_CA_CERT:-$REPO_ROOT/secrets/ec2_server.crt}"
export EC2_SSH_HOST="${EC2_SSH_HOST:-ubuntu@54.221.147.143}"
export EC2_SSH_KEY="${EC2_SSH_KEY:-$HOME/.ssh/weather-dev}"
export EC2_TUNNEL_PORT="${EC2_TUNNEL_PORT:-18443}"
# EC2 stream this run publishes to (packages + desk.json): e.g. EC2_STREAM_ID=japan -> page /s/japan/ on EC2.
# Empty = the default stream (the unprefixed page). Run one launcher per stream, each with its own RUN_ID.
export EC2_STREAM_ID="${EC2_STREAM_ID:-}"
export EC2_UPLOAD_TIMEOUT="${EC2_UPLOAD_TIMEOUT:-600}"

# ---- desk data (the website's live numbers, src/desk; also runnable alone: scripts/desk_update.sh) --
export DESK_ENABLED="${DESK_ENABLED:-1}"         # rebuild + publish desk.json next to the broadcast loop
export DESK_INTERVAL_S="${DESK_INTERVAL_S:-600}" # seconds between updates
export DESK_LLM="${DESK_LLM:-1}"                 # 1: warnings/impacts/headlines via Lumen (quote-checked); 0: numbers only
export DESK_STORM="${DESK_STORM:-}"              # storm to follow; empty = config storm.name
export DESK_JMA_TC="${DESK_JMA_TC:-TC2636}"      # fallback ids if storm discovery fails
export DESK_JTWC_ID="${DESK_JTWC_ID:-wp2926}"
export DESK_DIR="${DESK_DIR:-$REPO_ROOT/output/desk}"

# ---- process environment -----------------------------------------------------------------------
export PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

LOG_DIR="$REPO_ROOT/.run/livestream"
mkdir -p "$LOG_DIR" "$RUN_ROOT"
LOG_FILE="$LOG_DIR/$RUN_ID.log"
rm -f "$REPO_ROOT/.run/STOP"

log() { printf '%s  harness  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"; }

log "run $RUN_ID  mode=$MODE  max_hours=$MAX_HOURS  publish=$PUBLISH  dry_run=$DRY_RUN  log=$LOG_FILE"

if [[ ! -s "$LUMEN_KEYS_FILE" && -z "$LUMEN_API_KEYS" && -z "${LUMEN_API_KEY:-}" ]]; then
    log "WARNING: no Lumen API keys (LUMEN_API_KEYS / $LUMEN_KEYS_FILE); scraper and QC will use the local Qwen3 fallback"
fi

if [[ "$START_SERVICES" == "1" ]]; then
    bash "$REPO_ROOT/scripts/vllm_start.sh" 2>&1 | tee -a "$LOG_FILE" || { log "vLLM failed to start"; exit 1; }
    # MOSS-TTS only when this config has a scene that uses it (e.g. the Tagalog stream)
    if grep -q '"tts_model": *"moss' "$CONFIG_PATH"; then
        bash "$REPO_ROOT/scripts/moss_tts_start.sh" 2>&1 | tee -a "$LOG_FILE" || { log "MOSS TTS failed to start"; exit 1; }
    fi
    if [[ -x "$REPO_ROOT/scripts/searxng_start.sh" ]]; then
        bash "$REPO_ROOT/scripts/searxng_start.sh" 2>&1 | tee -a "$LOG_FILE" || log "WARNING: SearXNG failed to start; web search will be unavailable"
    fi
fi

if [[ "$ICRN_KEEPALIVE" == "1" && -x "$HOME/icrn_scripts/icrn-keepalive" ]]; then
    "$HOME/icrn_scripts/icrn-keepalive" start --match 'src/main.py' --max-hours "$(( ${MAX_HOURS%.*} + 1 ))" >>"$LOG_FILE" 2>&1 || true
fi

ARGS=(--mode "$MODE")
[[ "$DRY_RUN" == "1" ]] && ARGS+=(--dry-run)
[[ "$PUBLISH" != "1" ]] && ARGS+=(--no-publish)
[[ -n "$SCENES" ]] && ARGS+=(--scenes "$SCENES")

deadline=$(( $(date +%s) + ${MAX_HOURS%.*} * 3600 + 60 ))
attempt=0
while :; do
    attempt=$((attempt + 1))
    log "starting src/main.py (attempt $attempt)"
    "$PY" "$REPO_ROOT/src/main.py" "${ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
    rc=${PIPESTATUS[0]}
    if [[ $rc -eq 0 || $rc -eq 130 ]]; then
        log "main.py exited cleanly (rc=$rc)"; break
    fi
    if [[ -f "$REPO_ROOT/.run/STOP" ]]; then
        log "stop requested; not restarting"; break
    fi
    if (( $(date +%s) >= deadline )); then
        log "time limit reached; not restarting"; break
    fi
    if (( attempt >= RESTART_LIMIT )); then
        log "giving up after $attempt attempts"; exit "$rc"
    fi
    # exponential-ish back-off: 30s, 60s, 120s, ... capped at 10 min; vLLM is re-checked each time
    wait=$(( 30 * (1 << (attempt < 6 ? attempt - 1 : 5)) )); (( wait > 600 )) && wait=600
    log "main.py crashed (rc=$rc); resuming run $RUN_ID in ${wait}s"
    sleep "$wait"
    [[ "$START_SERVICES" == "1" ]] && bash "$REPO_ROOT/scripts/vllm_start.sh" >>"$LOG_FILE" 2>&1
done
log "done"

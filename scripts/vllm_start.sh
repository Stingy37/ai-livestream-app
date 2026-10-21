#!/usr/bin/env bash
# Start the local vLLM server that serves Qwen3-8B (fp8, online-quantised) plus the
# dynamic-RAG LoRA adapter trained in ~/grpo-rl-usal (results/2026-10-17_train_v5_s0, step 60).
#
# Every setting is an environment variable with the default shown, so scripts/run_livestream.sh
# can override them. The server is OpenAI-compatible:
#   base model ........ model="qwen3-8b"   (LOCAL_LLM_MODEL)
#   base + LoRA ....... model="dynrag"     (LORA_NAME)   -> used by the script writer
#
# Idempotent: exits 0 if a server started by this script is already running.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VLLM_BIN="${VLLM_BIN:-/home/andyshi2/.conda/envs/ai-livestream/bin/vllm}"
LOCAL_LLM_MODEL_PATH="${LOCAL_LLM_MODEL_PATH:-/home/andyshi2/pre-models/Qwen3-8B}"
LOCAL_LLM_MODEL="${LOCAL_LLM_MODEL:-qwen3-8b}"          # name clients pass as model=
LORA_PATH="${LORA_PATH:-$REPO_ROOT/model_weights/dynrag_lora_v5_step60}"
LORA_NAME="${LORA_NAME:-dynrag}"                       # model= name that applies the adapter
LORA_RANK="${LORA_RANK:-16}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
# Share of the MIG slice (~33 GB) vLLM may claim: fp8 weights (~9 GB) + KV cache. The rest is
# for the e5 encoder, Kokoro and CUDA contexts of the per-scene worker processes.
VLLM_GPU_MEM_UTIL="${VLLM_GPU_MEM_UTIL:-0.62}"
VLLM_QUANTIZATION="${VLLM_QUANTIZATION:-fp8}"          # same as the training rollouts
VLLM_KV_CACHE_DTYPE="${VLLM_KV_CACHE_DTYPE:-fp8}"
LOCAL_LLM_MAX_MODEL_LEN="${LOCAL_LLM_MAX_MODEL_LEN:-9216}"   # prompt + think + answer (grpo-rl-usal MAX_MODEL_LEN)
VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-32}"
VLLM_STARTUP_TIMEOUT="${VLLM_STARTUP_TIMEOUT:-900}"    # seconds
VLLM_RUN_DIR="${VLLM_RUN_DIR:-$REPO_ROOT/.run/vllm}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"                 # appended verbatim to `vllm serve`
# Sleep mode lets the harness park vLLM's weights in CPU RAM while the full MOSS-TTS model uses the GPU
# (src/models/gpu.py). Its /sleep and /wake_up endpoints need the server's dev mode; it listens on localhost only.
VLLM_SLEEP_MODE="${VLLM_SLEEP_MODE:-1}"
SLEEP_ARGS=""
if [[ "$VLLM_SLEEP_MODE" == "1" ]]; then export VLLM_SERVER_DEV_MODE=1; SLEEP_ARGS="--enable-sleep-mode"; fi

# FlashInfer's sampler JIT-compiles CUDA kernels on first use, which needs nvcc;
# this machine has no CUDA toolkit, so fall back to vLLM's PyTorch sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_LOGGING_LEVEL="${VLLM_LOGGING_LEVEL:-INFO}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TOKENIZERS_PARALLELISM=false

PID_FILE="$VLLM_RUN_DIR/vllm.pid"
LOG_FILE="$VLLM_RUN_DIR/vllm.log"

if [[ ! -x "$VLLM_BIN" ]]; then
    echo "vllm not found at $VLLM_BIN; set VLLM_BIN" >&2
    exit 1
fi
if [[ ! -f "$LORA_PATH/adapter_model.safetensors" ]]; then
    echo "LoRA adapter not found at $LORA_PATH (expected adapter_model.safetensors); set LORA_PATH" >&2
    exit 1
fi

mkdir -p "$VLLM_RUN_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    if curl -sf "http://$VLLM_HOST:$VLLM_PORT/health" >/dev/null 2>&1; then
        echo "vLLM already running (pid $(cat "$PID_FILE")) on port $VLLM_PORT"
        exit 0
    fi
    echo "vLLM pid $(cat "$PID_FILE") alive but not healthy yet; waiting for it"
else
    rm -f "$PID_FILE"
    if curl -sf "http://$VLLM_HOST:$VLLM_PORT/health" >/dev/null 2>&1; then
        echo "something is already serving on $VLLM_HOST:$VLLM_PORT (not started by this script)" >&2
        exit 1
    fi
    echo "starting vLLM: $LOCAL_LLM_MODEL_PATH as '$LOCAL_LLM_MODEL' (+LoRA '$LORA_NAME') on $VLLM_HOST:$VLLM_PORT"
    # setsid puts vLLM and its engine worker processes in their own process group,
    # so vllm_stop.sh can take down the whole group at once.
    # shellcheck disable=SC2086
    setsid "$VLLM_BIN" serve "$LOCAL_LLM_MODEL_PATH" \
        --served-model-name "$LOCAL_LLM_MODEL" \
        --host "$VLLM_HOST" \
        --port "$VLLM_PORT" \
        --dtype bfloat16 \
        --quantization "$VLLM_QUANTIZATION" \
        --kv-cache-dtype "$VLLM_KV_CACHE_DTYPE" \
        --gpu-memory-utilization "$VLLM_GPU_MEM_UTIL" \
        --max-model-len "$LOCAL_LLM_MAX_MODEL_LEN" \
        --max-num-seqs "$VLLM_MAX_NUM_SEQS" \
        --enable-lora \
        --max-lora-rank "$LORA_RANK" \
        --max-loras 1 \
        --lora-modules "$LORA_NAME=$LORA_PATH" \
        --enable-prefix-caching \
        --reasoning-parser qwen3 \
        $SLEEP_ARGS \
        $VLLM_EXTRA_ARGS \
        >"$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
fi

echo "waiting for server (log: $LOG_FILE)"
deadline=$((SECONDS + VLLM_STARTUP_TIMEOUT))
until curl -sf "http://$VLLM_HOST:$VLLM_PORT/health" >/dev/null 2>&1; do
    if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "vLLM exited during startup; last log lines:" >&2
        tail -n 30 "$LOG_FILE" >&2
        rm -f "$PID_FILE"
        exit 1
    fi
    if (( SECONDS >= deadline )); then
        echo "vLLM not ready after ${VLLM_STARTUP_TIMEOUT}s; stopping it. Last log lines:" >&2
        tail -n 30 "$LOG_FILE" >&2
        "$REPO_ROOT/scripts/vllm_stop.sh"
        exit 1
    fi
    sleep 3
done

echo "vLLM ready: http://$VLLM_HOST:$VLLM_PORT/v1 (pid $(cat "$PID_FILE")); models: $LOCAL_LLM_MODEL, $LORA_NAME"

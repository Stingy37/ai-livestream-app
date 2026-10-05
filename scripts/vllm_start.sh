set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

USER="andyshi2"
VLLM_BIN="/home/${USER}/.conda/envs/ai-livestream/bin/vllm"
LOCAL_LLM_MODEL_PATH="/home/${USER}/pre-models/Qwen3-8B"
LOCAL_LLM_MODEL="qwen3-8b"                # name clients pass as model=
VLLM_HOST="127.0.0.1"
VLLM_PORT="8000"
# Share of the WHOLE GPU vLLM may claim (weights + KV cache). The A100 is shared,
# so keep this to what is actually free; Qwen3-8B weights alone are ~16 GB.
VLLM_GPU_MEM_UTIL="0.27"
LOCAL_LLM_MAX_MODEL_LEN="8192"
VLLM_STARTUP_TIMEOUT="600"                # seconds
VLLM_RUN_DIR="$REPO_ROOT/.run/vllm"
VLLM_EXTRA_ARGS=""                        # appended verbatim to `vllm serve`

# FlashInfer's sampler JIT-compiles CUDA kernels on first use, which needs nvcc;
# this machine has no CUDA toolkit, so fall back to vLLM's PyTorch sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0

PID_FILE="$VLLM_RUN_DIR/vllm.pid"
LOG_FILE="$VLLM_RUN_DIR/vllm.log"

if [[ ! -x "$VLLM_BIN" ]]; then
    echo "vllm not found at $VLLM_BIN; fix VLLM_BIN at the top of this script" >&2
    exit 1
fi

mkdir -p "$VLLM_RUN_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "vLLM already running (pid $(cat "$PID_FILE")) on port $VLLM_PORT"
    exit 0
fi
rm -f "$PID_FILE"

if curl -sf "http://$VLLM_HOST:$VLLM_PORT/health" >/dev/null 2>&1; then
    echo "something is already serving on $VLLM_HOST:$VLLM_PORT (not started by this script)" >&2
    exit 1
fi

echo "starting vLLM: $LOCAL_LLM_MODEL_PATH as '$LOCAL_LLM_MODEL' on $VLLM_HOST:$VLLM_PORT"

# setsid puts vLLM and its engine worker processes in their own process group,
# so vllm_stop.sh can take down the whole group at once.
# shellcheck disable=SC2086
setsid "$VLLM_BIN" serve "$LOCAL_LLM_MODEL_PATH" \
    --served-model-name "$LOCAL_LLM_MODEL" \
    --host "$VLLM_HOST" \
    --port "$VLLM_PORT" \
    --gpu-memory-utilization "$VLLM_GPU_MEM_UTIL" \
    --max-model-len "$LOCAL_LLM_MAX_MODEL_LEN" \
    --reasoning-parser qwen3 \
    $VLLM_EXTRA_ARGS \
    >"$LOG_FILE" 2>&1 < /dev/null &
echo $! > "$PID_FILE"

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

echo "vLLM ready: http://$VLLM_HOST:$VLLM_PORT/v1 (pid $(cat "$PID_FILE"))"

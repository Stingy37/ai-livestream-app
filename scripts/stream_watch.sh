#!/usr/bin/env bash
# One health check of a running livestream; prints one status line, exits 1 (with the reasons) when something is wrong.
#
#   RUN_ID=jp-live-1 CONFIG_STEM=japan bash scripts/stream_watch.sh
#   RUN_ID=jp-live-1 bash scripts/stream_watch.sh --loop 120 1800   # check every 120 s; exit on a problem or after 1800 s
#   NO_PIPELINE=1 CONFIG_STEM=philippines EC2_STREAM_ID=philippines bash scripts/stream_watch.sh   # pipeline runs elsewhere
#
# Checks: pipeline launcher + harness, YouTube launcher + its last health line, encoder processes (Xvfb, chromium,
# ffmpeg), vLLM, SearXNG, the preview server and its EC2 data path, the desk updater's freshness, and that the
# harness log is still moving.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="${RUN_ID:-${NO_PIPELINE:+remote}}"; RUN_ID="${RUN_ID:?set RUN_ID}"; STEM="${CONFIG_STEM:-japan}"
LOG="$REPO_ROOT/.run/livestream/$RUN_ID.log"
YT_LOG="${YT_LOG:-$REPO_ROOT/.run/youtube/$STEM.console.log}"
QUIET_MIN="${QUIET_MIN:-45}"; DESK_MAX_MIN="${DESK_MAX_MIN:-25}"

age_min() { [[ -e "$1" ]] && echo $(( ( $(date +%s) - $(stat -c %Y "$1") ) / 60 )) || echo 9999; }

check() {
  local bad=() info=()
  # NO_PIPELINE=1: the pipeline runs on another machine (e.g. a teammate's server); watch only this side
  if [[ "${NO_PIPELINE:-0}" != 1 ]]; then
    pgrep -f "scripts/run_livestream.sh" >/dev/null || bad+=("pipeline launcher not running")
    pgrep -f "src/main.py" >/dev/null || bad+=("harness (main.py) not running")
    (( $(age_min "$LOG") <= QUIET_MIN )) || bad+=("harness log quiet for $(age_min "$LOG") min")
  fi
  if [[ "${NO_YOUTUBE:-0}" != 1 ]]; then
    pgrep -f "scripts/youtube_live.py" >/dev/null || bad+=("youtube_live.py not running")
    for p in Xvfb chromium ffmpeg; do pgrep -x "$p" >/dev/null || pgrep -f "/usr/bin/$p|^$p " >/dev/null || bad+=("encoder: $p not running"); done
    local h; h=$(grep -a "health" "$YT_LOG" 2>/dev/null | tail -n 1)
    info+=("yt: ${h##*INFO     }")
    [[ -n "$h" && "$h" != *"stream active"* ]] && bad+=("youtube: ${h##*INFO     }")
    [[ -n "$h" && "$h" == *"health bad"* ]] && bad+=("youtube health bad")
  fi
  curl -sf -m 5 http://127.0.0.1:8000/health >/dev/null || bad+=("vLLM not healthy")
  curl -sf -m 5 -o /dev/null "http://127.0.0.1:8890/" || bad+=("SearXNG down")
  local live="http://127.0.0.1:${PREVIEW_PORT:-8095}/${EC2_STREAM_ID:+s/$EC2_STREAM_ID/}live"
  curl -sf -m 10 -o /dev/null "$live/current.json" || bad+=("preview $live/current.json failing (EC2 tunnel?)")
  local gen; gen=$(curl -sf -m 10 "$live/desk.json" | python3 -c "import json,sys,datetime as d; g=json.load(sys.stdin)['generated_at']; print(int((d.datetime.now(d.timezone.utc)-d.datetime.fromisoformat(g.replace('Z','+00:00'))).total_seconds()//60))" 2>/dev/null)
  [[ -n "$gen" && "$gen" -le "$DESK_MAX_MIN" ]] || bad+=("desk.json stale (${gen:-?} min)")
  # a stage that started but whose workers have been silent for STALL_MIN (the broadcast loop keeps the log itself busy)
  local stall; stall=$(tail -n 3000 "$LOG" 2>/dev/null | python3 -c '
import sys, re, datetime as d
last_stage = last_pid = None
for ln in sys.stdin:
    m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", ln)
    if not m: continue
    t = d.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    if re.search(r"\] (starting \d+ scene process|complete:)", ln): last_stage = (t, "complete:" in ln)
    if "[pid " in ln: last_pid = t
if last_stage and not last_stage[1]:
    ref = max(x for x in (last_stage[0], last_pid) if x)
    print(int((d.datetime.now() - ref).total_seconds() // 60))
' 2>/dev/null)
  [[ -n "$stall" && "$stall" -gt "${STALL_MIN:-20}" ]] && bad+=("pipeline stage stalled: no worker output for $stall min")
  local pkg; pkg=$(grep -a "published and activated" "$LOG" 2>/dev/null | tail -n 1 | sed -E 's/.*package ([^ ]+) published.*/\1/')
  info+=("pkg ${pkg:-none}" "desk ${gen:-?}m" "log $(age_min "$LOG")m")
  local errs; errs=$(grep -ac "ERROR" "$LOG" 2>/dev/null); info+=("errors $errs")
  echo "$(date -u +%H:%M:%SZ) ${bad[*]:+PROBLEM: $(IFS=';'; echo "${bad[*]}") | }${info[*]}"
  (( ${#bad[@]} == 0 ))
}

if [[ "${1:-}" == "--loop" ]]; then
  every="${2:-120}"; total="${3:-1800}"; end=$(( $(date +%s) + total )); fails=0
  while (( $(date +%s) < end )); do
    if out=$(check); then fails=0; last="$out"; else
      fails=$((fails + 1)); last="$out"
      (( fails >= ${FAIL_CHECKS:-2} )) && { echo "$out"; exit 1; }     # two failing checks in a row: report
    fi
    sleep "$every"
  done
  echo "$last"; exit 0
fi
check

#!/usr/bin/env bash
# Election night: the three YouTube encoders (election-es, election-ja, election-zh) side by side.
#
#   ELECTION_PRIVACY=public bash scripts/election_encoders.sh start [es ja zh]   # LIVE to YouTube
#   bash scripts/election_encoders.sh stop [es ja zh]       # ends the broadcast(s) (touch .run/STOP_YOUTUBE_election-<lang>)
#   bash scripts/election_encoders.sh reload <lang>         # restart one encoder (page reload); ~1 min gap on that stream
#   bash scripts/election_encoders.sh status
#   bash scripts/election_encoders.sh test [seconds] [es ja zh]   # local 1080p30 files, output/election_encoder_test/; no YouTube
#
# start: for each language runs scripts/youtube_live.py --config saved_configs/election_<lang>.json --lang <lang>
#   --stream election-<lang> --hours $ELECTION_HOURS --refresh-min 0. That is the normal youtube_live.py flow: it reuses the
#   broadcast prepared by scripts/election_youtube.py --create (.run/youtube/election_<lang>.json), binds it to its own
#   ingest stream, reads the RTMPS URL + stream key from the YouTube API and starts scripts/encoder.sh with them. The key
#   lives only in that process's environment: this script never prints or logs it (logs shown here are masked).
#   A language without a prepared broadcast is refused: youtube_live.py would otherwise make one with the typhoon
#   desk's thumbnail and metadata. ELECTION_PRIVACY (public | unlisted | private) must be set explicitly.
# Each encoder: own Xvfb display, PulseAudio port and Chromium profile (scripts/encoder.sh derives them from the stream id),
# page http://127.0.0.1:$PREVIEW_PORT/s/election-<lang>/?autoplay=1&lang=<lang> from scripts/web_preview.py.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
RUN_DIR="$REPO_ROOT/.run/election"
HOURS="${ELECTION_HOURS:-11}"
STAGGER_S="${ELECTION_ENCODER_STAGGER_S:-20}"        # Chromium start-up is the CPU peak: do not start all three at once
mkdir -p "$RUN_DIR"
cmd="${1:-status}"; shift || true
mask() { sed -E 's#(rtmps?://[^ ]*/live2/)[^ "]+#\1<key>#g; s#(streamName["'"'"': =]+)[A-Za-z0-9_-]+#\1<key>#g'; }
yt_alive() { local p="$RUN_DIR/youtube_$1.pid"; [[ -f "$p" ]] && kill -0 "$(cat "$p")" 2>/dev/null \
             && tr '\0' ' ' < "/proc/$(cat "$p")/cmdline" 2>/dev/null | grep -q "youtube_live.py"; }
enc_pgid() { local pid; for pid in $(pgrep -f "yt-encoder" || true); do
               tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "s/election-$1/" && { ps -o pgid= -p "$pid" | tr -d ' '; return; }
             done; }
langs() { if (( $# )); then echo "$@"; else echo "es ja zh"; fi; }
# The preview server must run in its own session: if encoder.sh started it, it would sit in that encoder's process
# group, and stopping/reloading that one encoder (killpg) would take the page server down for all three streams.
ensure_preview() {
  local url="http://127.0.0.1:${PREVIEW_PORT:-8095}/"
  curl -sf -o /dev/null "$url" && return 0
  setsid nohup bash "$REPO_ROOT/scripts/web_preview.sh" >>"$REPO_ROOT/.run/web_preview.log" 2>&1 < /dev/null &
  for _ in $(seq 1 20); do sleep 0.5; curl -sf -o /dev/null "$url" && { echo "preview server up: $url"; return 0; }; done
  echo "preview server did not start; see .run/web_preview.log" >&2; return 1
}

case "$cmd" in
  start)
    case "${ELECTION_PRIVACY:-}" in public|unlisted|private) ;; *)
      echo "set ELECTION_PRIVACY=public|unlisted|private (explicitly) to go live" >&2; exit 2 ;; esac
    ensure_preview
    first=1
    for l in $(langs "$@"); do
      cfg="$REPO_ROOT/saved_configs/election_$l.json"
      [[ -f "$cfg" ]] || { echo "$l: missing $cfg" >&2; continue; }
      [[ -f "$REPO_ROOT/.run/youtube/election_$l.json" ]] || {
        echo "$l: no prepared broadcast (.run/youtube/election_$l.json); run scripts/election_youtube.py --create --lang $l first" >&2; continue; }
      if yt_alive "$l"; then echo "$l: already live (pid $(cat "$RUN_DIR/youtube_$l.pid"))"; continue; fi
      (( first )) || sleep "$STAGGER_S"; first=0
      title="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["youtube"]["title"])' "$cfg")"
      YOUTUBE_TITLE="$title" EC2_STREAM_ID="election-$l" nohup "$PY" "$REPO_ROOT/scripts/youtube_live.py" \
        --config "$cfg" --lang "$l" --stream "election-$l" --privacy "$ELECTION_PRIVACY" --hours "$HOURS" --refresh-min 0 \
        >>"$RUN_DIR/youtube_$l.log" 2>&1 < /dev/null &
      echo $! > "$RUN_DIR/youtube_$l.pid"
      echo "$l: youtube_live.py started (pid $!, $ELECTION_PRIVACY, ${HOURS} h); log $RUN_DIR/youtube_$l.log"
    done ;;
  stop)
    for l in $(langs "$@"); do
      touch "$REPO_ROOT/.run/STOP_YOUTUBE_election-$l"
      echo "$l: stop requested; youtube_live.py ends the broadcast and the encoder within ~60 s"
    done ;;
  reload)
    l="${1:?usage: reload <es|ja|zh>}"
    g="$(enc_pgid "$l")"
    [[ -n "$g" ]] || { echo "$l: no encoder running" >&2; exit 1; }
    kill -TERM -- "-$g" && echo "$l: encoder (pgid $g) stopped; youtube_live.py restarts it within 60 s"
    ;;
  status)
    for l in es ja zh; do
      air="$REPO_ROOT/output/election/air/election-$l"
      printf '%s: youtube_live %s, encoder %s' "$l" "$(yt_alive "$l" && echo "up (pid $(cat "$RUN_DIR/youtube_$l.pid"))" || echo down)" \
        "$([[ -n "$(enc_pgid "$l")" ]] && echo up || echo down)"
      if [[ -f "$air/playback.json" ]]; then
        printf ', page heartbeat %ss ago' "$(( $(date +%s) - $(stat -c %Y "$air/playback.json") ))"
      else printf ', no page heartbeat yet'; fi
      printf ', on air %s\n' "$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("package_id"))' "$air/current.json" 2>/dev/null || echo none)"
      [[ -f "$RUN_DIR/youtube_$l.log" ]] && tail -n 2 "$RUN_DIR/youtube_$l.log" | mask | sed 's/^/    /'
      [[ -f "$REPO_ROOT/.run/encoder/election-$l/ffmpeg.log" ]] && tail -n 1 "$REPO_ROOT/.run/encoder/election-$l/ffmpeg.log" | mask | sed 's/^/    ffmpeg: /'
    done ;;
  test)
    dur=60; [[ "${1:-}" =~ ^[0-9]+$ ]] && { dur="$1"; shift; }
    out="$REPO_ROOT/output/election_encoder_test"; mkdir -p "$out"; tag="$(date -u +%H%M%S)"
    ensure_preview
    pids=()
    for l in $(langs "$@"); do
      EC2_STREAM_ID="election-$l" STREAM_LANG="$l" DURATION="$dur" OUT="$out/${tag}_$l.mp4" \
        bash "$REPO_ROOT/scripts/encoder.sh" >"$RUN_DIR/encoder_test_$l.log" 2>&1 &
      pids+=($!); sleep 2
    done
    echo "recording ${dur}s for: $(langs "$@") (files $out/${tag}_<lang>.mp4)"
    wait "${pids[@]}" || true
    ls -la "$out"/"${tag}"_*.mp4 ;;
  *) echo "usage: $0 start|stop|reload|status|test" >&2; exit 2 ;;
esac

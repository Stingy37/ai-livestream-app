#!/usr/bin/env bash
# Render the stream page and push it to YouTube (or record a test file), from this ICRN box.
#
#   OUT=/home/andyshi2/ai-livestream-app/output/encoder_test.mp4 DURATION=20 bash scripts/encoder.sh   # test file
#   OUT="rtmps://a.rtmps.youtube.com/live2/<key>" bash scripts/encoder.sh                          # live
#   (scripts/youtube_live.py fills OUT from the YouTube Data API.)
#
# The page is the local preview server by default (it serves html/ from disk and proxies live data and audio
# from EC2), so the stream shows the newest page without deploying. Runs in the udocker container
# "yt-encoder" (Debian + Chromium + Xvfb + PulseAudio + ffmpeg); see scripts/encoder/inside.sh.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
U="${UDOCKER:-/home/andyshi2/.local/bin/udocker}"
export UDOCKER_CONTAINERS="${UDOCKER_CONTAINERS:-$HOME/.udocker/containers-persist}"   # see scripts/encoder/build.sh
# EC2_STREAM_ID picks the stream's page (/s/<id>/); unset or "default" is the unprefixed page
STREAM_PATH=""; [[ -n "${EC2_STREAM_ID:-}" && "${EC2_STREAM_ID}" != "default" ]] && STREAM_PATH="s/${EC2_STREAM_ID}/"
export URL="${ENCODER_URL:-http://127.0.0.1:${PREVIEW_PORT:-8095}/${STREAM_PATH}?autoplay=1${STREAM_LANG:+&lang=$STREAM_LANG}}"
export OUT="${OUT:?set OUT to an rtmp(s):// URL with the stream key, or a .mp4 file path}"
[[ "$OUT" == "$REPO_ROOT"/* ]] && OUT="/app/${OUT#"$REPO_ROOT"/}"   # the repo is mounted at /app inside the container
# encoders side by side: each stream gets its own virtual display, PulseAudio port, Chromium profile and log folder
# (derived from EC2_STREAM_ID; DISPLAY_NUM / PULSE_PORT override). The default stream keeps :99 / 24713.
if [[ -n "${EC2_STREAM_ID:-}" && "${EC2_STREAM_ID}" != "default" ]]; then
  N=$(( $(printf '%s' "$EC2_STREAM_ID" | cksum | cut -d' ' -f1) % 400 ))
  DISPLAY_NUM="${DISPLAY_NUM:-$(( 100 + N ))}"; PULSE_PORT="${PULSE_PORT:-$(( 24800 + N ))}"
  LOGDIR="$REPO_ROOT/.run/encoder/$EC2_STREAM_ID"
else
  LOGDIR="$REPO_ROOT/.run/encoder"
fi
mkdir -p "$LOGDIR"
# the preview server must be up (it is also the page's data proxy to EC2)
curl -sf -o /dev/null "http://127.0.0.1:${PREVIEW_PORT:-8095}/" || { nohup bash "$REPO_ROOT/scripts/web_preview.sh" >"$REPO_ROOT/.run/web_preview.log" 2>&1 & sleep 3; }
"$U" setup --execmode="${UDOCKER_MODE:-P1}" yt-encoder >/dev/null 2>&1 || true
# runtime files (X socket, PulseAudio, Chromium profile) go to the host's local /tmp: on the network home disk the
# container's own /tmp shows as owned by nobody, which PulseAudio refuses
exec "$U" run --nobanner -v /tmp:/tmp -v "$REPO_ROOT:/app" -v "$LOGDIR:/logs" \
  --env="URL=$URL" --env="OUT=$OUT" --env="LOGDIR=/logs" --env="DURATION=${DURATION:-0}" --env="FPS=${FPS:-30}" \
  --env="VBITRATE=${VBITRATE:-4500k}" --env="PRESET=${PRESET:-veryfast}" --env="WARMUP=${WARMUP:-10}" --env="PULSE_PORT=${PULSE_PORT:-24713}" --env="DISPLAY_NUM=${DISPLAY_NUM:-99}" \
  yt-encoder /bin/bash /app/scripts/encoder/inside.sh

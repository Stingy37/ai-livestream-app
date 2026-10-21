#!/bin/bash
# Runs INSIDE the yt-encoder container (started by scripts/encoder.sh). Renders the stream page in Chromium on
# a virtual display, sends its audio to a PulseAudio null sink, and encodes both with ffmpeg to $OUT
# (an rtmp(s):// URL or a file). Each component is restarted if it dies.
set -u
: "${URL:?}" "${OUT:?}"
W=${WIDTH:-1920}; H=${HEIGHT:-1080}; FPS=${FPS:-30}; VBITRATE=${VBITRATE:-4500k}; ABITRATE=${ABITRATE:-128k}
PRESET=${PRESET:-veryfast}; DURATION=${DURATION:-0}; LOG=${LOGDIR:-/tmp}
# PulseAudio over TCP on localhost: proot (udocker P1) breaks the credential passing of its Unix socket
PULSE_PORT=${PULSE_PORT:-24713}
DISP=${DISPLAY_NUM:-99}     # one virtual display per encoder (scripts/encoder.sh picks it per stream)
# HOME and the runtime dir on the host's local /tmp (mounted by encoder.sh): PulseAudio refuses directories on the
# network home disk, which show as owned by nobody. One set per PULSE_PORT, so encoders can run side by side.
export HOME=/tmp/encoder-home-$PULSE_PORT XDG_RUNTIME_DIR=/tmp/encoder-run-$PULSE_PORT DISPLAY=:$DISP
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
export PULSE_SERVER=tcp:127.0.0.1:$PULSE_PORT PULSE_SINK=out
# no D-Bus in the container: an inherited session-bus address makes PulseAudio wait ~25 s per lookup
unset DBUS_SESSION_BUS_ADDRESS; export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent

start_x() { mkdir -p /tmp/.X11-unix 2>/dev/null; chmod 1777 /tmp/.X11-unix 2>/dev/null; Xvfb :$DISP -screen 0 ${W}x${H}x24 -nolisten tcp -ac >"$LOG/xvfb.log" 2>&1 & XPID=$!; }
start_pulse() {
  pulseaudio --daemonize=no --exit-idle-time=-1 --disallow-exit=1 -n --use-pid-file=no --realtime=no --high-priority=no \
    --disable-shm=yes --load="module-native-protocol-tcp listen=127.0.0.1 port=$PULSE_PORT auth-anonymous=1" \
    --load="module-null-sink sink_name=out sink_properties=device.description=stream-audio" \
    --load="module-always-sink" >"$LOG/pulse.log" 2>&1 & PPID_=$!
}
start_chrome() {
  rm -rf /tmp/chrome-profile-$DISP/Singleton* 2>/dev/null
  chromium --no-sandbox --kiosk --window-position=0,0 --window-size=${W},${H} --force-device-scale-factor=1 \
    --autoplay-policy=no-user-gesture-required --no-first-run --no-default-browser-check --disable-features=Translate,TranslateUI --disable-translate \
    --disable-session-crashed-bubble --disable-infobars --ignore-certificate-errors --hide-scrollbars \
    --user-data-dir=/tmp/chrome-profile-$DISP --alsa-output-device=pulse "$URL" >"$LOG/chrome.log" 2>&1 & CPID=$!
}
start_ffmpeg() {
  local fmt=flv; [[ "$OUT" == *.mp4 || "$OUT" == *.mkv ]] && fmt=${OUT##*.} && fmt=${fmt/mkv/matroska}
  local dur=(); (( DURATION > 0 )) && dur=(-t "$DURATION")
  ffmpeg -hide_banner -loglevel warning -nostdin -y \
    -thread_queue_size 1024 -f x11grab -draw_mouse 0 -framerate "$FPS" -video_size ${W}x${H} -i :$DISP \
    -thread_queue_size 1024 -f pulse -i out.monitor \
    -c:v libx264 -preset "$PRESET" -b:v "$VBITRATE" -maxrate "$VBITRATE" -bufsize 9000k -pix_fmt yuv420p \
    -g $((FPS * 2)) -keyint_min $((FPS * 2)) -sc_threshold 0 \
    -c:a aac -b:a "$ABITRATE" -ar 44100 -ac 2 "${dur[@]}" -f "$fmt" "$OUT" >"$LOG/ffmpeg.log" 2>&1 & FPID=$!
}

wait_for() { local i; for i in $(seq 1 120); do [[ -e "$1" ]] && return 0; sleep 0.5; done; echo "timed out waiting for $1"; return 1; }
pulse_up() { local i; for i in $(seq 1 60); do (echo > /dev/tcp/127.0.0.1/$PULSE_PORT) 2>/dev/null && return 0; sleep 0.5; done; echo "pulseaudio did not open port $PULSE_PORT"; }
start_x; wait_for /tmp/.X11-unix/X$DISP; start_pulse; pulse_up; sleep 1
start_chrome; sleep "${WARMUP:-10}"; start_ffmpeg
echo "encoder up: $URL -> ${OUT%%/live2/*}$( [[ $OUT == *live2/* ]] && echo '/live2/<key>')"
while :; do
  sleep 5
  kill -0 $XPID 2>/dev/null || { echo "Xvfb died; restarting"; start_x; sleep 1; }
  kill -0 $PPID_ 2>/dev/null || { echo "pulseaudio died; restarting"; start_pulse; sleep 2; }
  kill -0 $CPID 2>/dev/null || { echo "chromium died; restarting"; start_chrome; sleep 8; }
  if ! kill -0 $FPID 2>/dev/null; then
    (( DURATION > 0 )) && { echo "recording finished"; break; }
    echo "ffmpeg exited; restarting in 3s"; tail -n 3 "$LOG/ffmpeg.log"; sleep 3; start_ffmpeg
  fi
done
kill $CPID $PPID_ $XPID 2>/dev/null

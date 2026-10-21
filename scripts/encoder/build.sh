#!/usr/bin/env bash
# Build the udocker container "yt-encoder" (Debian bookworm + Chromium + Xvfb + PulseAudio + ffmpeg + CJK fonts)
# that scripts/encoder.sh runs. Containers live on the persistent home disk (UDOCKER_CONTAINERS), not under /tmp:
# ICRN restarts wipe /tmp, and ~/.udocker/containers used to point there.
#
#   bash scripts/encoder/build.sh          # ~10 min; safe to re-run (skips when the container works)
set -euo pipefail
U="${UDOCKER:-/home/andyshi2/.local/bin/udocker}"
export UDOCKER_CONTAINERS="${UDOCKER_CONTAINERS:-$HOME/.udocker/containers-persist}"
mkdir -p "$UDOCKER_CONTAINERS"
if "$U" run --nobanner yt-encoder /bin/sh -c "command -v chromium && command -v ffmpeg && command -v Xvfb && command -v pulseaudio" >/dev/null 2>&1; then
  echo "yt-encoder already works ($UDOCKER_CONTAINERS)"; exit 0
fi
"$U" pull debian:bookworm-slim
"$U" create --name=yt-encoder debian:bookworm-slim 2>/dev/null || echo "container yt-encoder exists; reinstalling packages"
"$U" setup --execmode=P1 yt-encoder
# systemd/dbus come in as dependencies; their post-install scripts rename files in /etc, which fails under proot on
# the network home disk ("Invalid cross-device link"). The encoder never runs them, so they are made no-ops.
"$U" run --nobanner --user=root yt-encoder /bin/bash -c '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  noop() { for f in /var/lib/dpkg/info/systemd.postinst /var/lib/dpkg/info/systemd-sysv.postinst /var/lib/dpkg/info/dbus.postinst; do
             [ -f $f ] && printf "#!/bin/sh\nexit 0\n" > $f; done; true; }
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends chromium xvfb pulseaudio ffmpeg ca-certificates \
      fonts-noto-cjk fonts-noto-color-emoji fonts-dejavu-core procps >/dev/null || { noop; dpkg --configure -a; \
  apt-get install -y -qq --no-install-recommends chromium xvfb pulseaudio ffmpeg ca-certificates \
      fonts-noto-cjk fonts-noto-color-emoji fonts-dejavu-core procps >/dev/null; }
  command -v chromium ffmpeg Xvfb pulseaudio'
echo "yt-encoder ready in $UDOCKER_CONTAINERS"

#!/usr/bin/env bash
# Open (or reuse) an SSH local port forward to the EC2 broadcast server, for when the security
# group does not expose port 8443 directly:  local https://127.0.0.1:${LOCAL_PORT}/ -> EC2 :8443
#
#   bash scripts/ec2_tunnel.sh            # start (idempotent), prints the local url
#   bash scripts/ec2_tunnel.sh stop
#   bash scripts/ec2_tunnel.sh status
#
# The publisher (src/broadcast/publisher.py) runs the same command itself when the direct url is
# unreachable; this script is for humans who want to look at the site from ICRN or a laptop.
set -euo pipefail
EC2_SSH_HOST="${EC2_SSH_HOST:-ubuntu@54.221.147.143}"
EC2_SSH_KEY="${EC2_SSH_KEY:-$HOME/.ssh/weather-dev}"
EC2_PORT="${EC2_PORT:-8443}"
LOCAL_PORT="${LOCAL_PORT:-${EC2_TUNNEL_PORT:-18443}}"
cmd="${1:-start}"

pids() { pgrep -f -- "ssh .*-L ${LOCAL_PORT}:127.0.0.1:${EC2_PORT} .*${EC2_SSH_HOST#*@}" || true; }
alive() { curl -sk --max-time 4 "https://127.0.0.1:${LOCAL_PORT}/healthz" 2>/dev/null | grep -q '"ok": true'; }

case "$cmd" in
  start)
    if alive; then echo "tunnel already up: https://127.0.0.1:${LOCAL_PORT}/"; exit 0; fi
    ssh -N -f -o IdentitiesOnly=yes -o PasswordAuthentication=no -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new \
        -i "$EC2_SSH_KEY" -L "${LOCAL_PORT}:127.0.0.1:${EC2_PORT}" "$EC2_SSH_HOST"
    for i in $(seq 1 15); do alive && { echo "tunnel up: https://127.0.0.1:${LOCAL_PORT}/"; exit 0; }; sleep 1; done
    echo "tunnel started but the server is not answering on https://127.0.0.1:${LOCAL_PORT}/healthz" >&2; exit 1 ;;
  stop)
    p="$(pids)"; [[ -n "$p" ]] && kill $p && echo "tunnel stopped" || echo "no tunnel running" ;;
  status)
    if alive; then echo "up: https://127.0.0.1:${LOCAL_PORT}/ (pids: $(pids | tr '\n' ' '))"; else echo "down"; exit 1; fi ;;
  *) echo "usage: $0 [start|stop|status]" >&2; exit 2 ;;
esac

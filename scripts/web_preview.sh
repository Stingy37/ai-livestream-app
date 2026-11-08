#!/usr/bin/env bash
# Preview the broadcast website locally with live EC2 data: edit html/champi-desk.html, refresh the browser.
#   bash scripts/web_preview.sh                  # http://127.0.0.1:8095/
#   PREVIEW_PORT=8099 bash scripts/web_preview.sh
# Ctrl+C stops it. Push your edits to the real site with: bash ec2/deploy.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
bash "$REPO_ROOT/scripts/ec2_tunnel.sh" >/dev/null || echo "warning: tunnel to EC2 is down; the page will load but show no live data" >&2
exec "$PY" "$REPO_ROOT/scripts/web_preview.py"

#!/usr/bin/env bash
# Rebuild the website's live numbers (desk.json) from JMA, JTWC, PAGASA, CWA and the NCEP ensembles,
# and publish them to EC2 (GET /live/desk.json). Runs by itself; the harness also runs it every 10 min.
#   bash scripts/desk_update.sh               # one update, published
#   bash scripts/desk_update.sh --no-publish  # write output/desk/desk.json only
#   bash scripts/desk_update.sh --loop        # every DESK_INTERVAL_S (600) seconds until Ctrl+C
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export LUMEN_KEYS_FILE="${LUMEN_KEYS_FILE:-$REPO_ROOT/secrets/lumen_keys.txt}"
exec "$PY" -m desk.updater "$@"

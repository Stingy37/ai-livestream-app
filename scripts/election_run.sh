#!/usr/bin/env bash
# Election-night script/voice runners, one per stream (src/election/run.py), restarted if they crash.
#
#   bash scripts/election_run.sh start [es ja zh]     # default: all three
#   bash scripts/election_run.sh stop  [es ja zh]     # stops after the scene being generated
#   bash scripts/election_run.sh status
#
# Logs: .run/election/election-<lang>.log. Output: output/election/air/election-<lang>/ (served by web_preview.py).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=/home/andyshi2/.conda/envs/ai-livestream/bin/python
RUN="$REPO/.run/election"; mkdir -p "$RUN"
cmd="${1:-status}"; shift || true
langs=("$@"); [[ ${#langs[@]} -eq 0 ]] && langs=(es ja zh)

supervise() {   # $1 = lang
  local l="$1" s="election-$1"
  while [[ ! -e "$REPO/.run/STOP_ELECTION_$s" ]]; do
    (cd "$REPO/src" && exec "$P" -m election.run --lang "$l" --stream "$s") >>"$RUN/$s.log" 2>&1
    [[ -e "$REPO/.run/STOP_ELECTION_$s" ]] && break
    echo "$(date -u +%FT%TZ) runner exited ($?); restarting in 10 s" >>"$RUN/$s.log"; sleep 10
  done
}

case "$cmd" in
  start)
    for l in "${langs[@]}"; do
      s="election-$l"; rm -f "$REPO/.run/STOP_ELECTION_$s"
      if [[ -f "$RUN/$s.pid" ]] && kill -0 "$(cat "$RUN/$s.pid")" 2>/dev/null; then echo "$s already running"; continue; fi
      setsid bash -c "$(declare -f supervise); REPO=$REPO P=$P RUN=$RUN supervise $l" </dev/null >/dev/null 2>&1 &
      echo $! >"$RUN/$s.pid"; echo "$s started (supervisor pid $!)"
    done ;;
  stop)
    for l in "${langs[@]}"; do touch "$REPO/.run/STOP_ELECTION_election-$l"; echo "election-$l: stop requested"; done ;;
  status)
    for l in es ja zh; do
      s="election-$l"; pid=$(cat "$RUN/$s.pid" 2>/dev/null || echo -)
      alive=$([[ "$pid" != - ]] && kill -0 "$pid" 2>/dev/null && echo up || echo down)
      cur="$REPO/output/election/air/$s/current.json"
      pkg=$([[ -f "$cur" ]] && "$P" -c "import json;m=json.load(open('$cur'));print(m['package_id'], len(m['scenes']), 'scenes', m['created_at'])" || echo "no package")
      echo "$s: $alive · $pkg"; grep -h "INFO \[$s\]\|WARNING \[$s\]" "$RUN/$s.log" 2>/dev/null | tail -2 | cut -c1-200
    done ;;
  *) echo "usage: $0 start|stop|status [es ja zh]"; exit 2 ;;
esac

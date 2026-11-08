#!/bin/bash
# Usage: watch_lab.sh HH:MM [plan.json]. Wake the operator: exit with a report at UNTIL (UTC "HH:MM", same or next day), or earlier on a new problem line.
cd /home/andyshi2/ai-livestream-app
UNTIL="$1"
PLAN="${2:-plan_arnab2.json}"
OUT="research/market/$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["out"])' research/market/title_lab/$PLAN)"
F=".run/youtube/india_te.console.log .run/youtube/india_ta.console.log .run/livestream/in-te-1.log .run/livestream/in-ta-1.log research/market/title_lab/lab.log"
PAT='ERROR|Traceback|crashed|encoder exited|refresh failed|update failed|NOT updated|quotaExceeded|health (bad|noData)|ending broadcast'
declare -A base; for f in $F; do touch $f; base[$f]=$(wc -l < $f); done
target=$(date -u -d "$UNTIL" +%s); [ "$target" -lt "$(date -u +%s)" ] && target=$((target + 86400))
while [ "$(date -u +%s)" -lt "$target" ]; do
  for f in $F; do
    n=$(wc -l < $f)
    if [ "$n" -gt "${base[$f]}" ]; then
      hit=$(tail -n +$((${base[$f]}+1)) $f | grep -a -E "$PAT" | grep -av "invalidTransition" | head -3)
      base[$f]=$n
      [ -n "$hit" ] && { echo "PROBLEM in $f"; echo "$hit" | cut -c1-260; exit 0; }
    fi
  done
  [ -f $OUT/errors.csv ] && [ "$(wc -l < $OUT/errors.csv)" -gt "${E:-0}" ] && { E=$(wc -l < $OUT/errors.csv); echo "lab error:"; tail -n 1 $OUT/errors.csv; exit 0; }
  sleep 60
done
echo "REPORT at $(date -u +%H:%M)Z"
cd research/market && /home/andyshi2/.conda/envs/ai-livestream/bin/python title_lab.py title_lab/$PLAN --report
tail -n 2 ../../$OUT/panel.csv

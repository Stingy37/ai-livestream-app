#!/usr/bin/env bash
# Round 2: 14 cells now (what is left of today's YouTube quota), the rest after the quota reset at 07:00 UTC.
cd "$(dirname "$0")"
P=/home/andyshi2/.conda/envs/ai-livestream/bin/python
echo "=== batch 1 $(date -u +%FT%TZ)"
$P measure.py round2.json --cache cache3 --max-searches 14 2>&1 | grep -v Warning | cut -c1-170
now=$(date -u +%s); at=$(date -u -d "tomorrow 07:05" +%s); [[ $(date -u +%H) -lt 7 ]] && at=$(date -u -d "today 07:05" +%s)
echo "=== sleeping $(( (at - now) / 60 )) min until $(date -u -d @$at +%FT%TZ)"
sleep $(( at - now ))
echo "=== batch 2 $(date -u +%FT%TZ)"
$P measure.py round2.json --cache cache3 2>&1 | grep -v Warning | cut -c1-170
echo "=== done $(date -u +%FT%TZ)"

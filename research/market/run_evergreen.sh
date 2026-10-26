#!/usr/bin/env bash
# Two snapshots of always-on live streams at different times of day, on two separate quota days.
cd "$(dirname "$0")"
P=/home/andyshi2/.conda/envs/ai-livestream/bin/python
for at in "2026-10-23 12:00" "2026-10-24 08:00"; do
  t=$(date -u -d "$at" +%s); now=$(date -u +%s); (( t > now )) && sleep $(( t - now ))
  echo "=== snapshot $(date -u +%FT%TZ)"; $P live_now.py evergreen.json 2>&1 | grep -v Warning | cut -c1-200
done
echo "=== done $(date -u +%FT%TZ)"

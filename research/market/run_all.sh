#!/usr/bin/env bash
cd "$(dirname "$0")"
P=/home/andyshi2/.conda/envs/ai-livestream/bin/python
for job in "conflict.json" "other.json" "shortlist.json --cache cache2"; do
  echo "=== $job $(date -u +%H:%M:%S)"
  $P measure.py $job 2>&1 | grep -v Warning | cut -c1-170
done
echo "=== done $(date -u +%H:%M:%S)"

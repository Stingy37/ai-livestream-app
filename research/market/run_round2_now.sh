#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "=== start $(date -u +%FT%TZ)"
/home/andyshi2/.conda/envs/ai-livestream/bin/python measure.py round2.json --cache cache3 2>&1 | grep -v Warning | cut -c1-200
echo "=== done $(date -u +%FT%TZ)"

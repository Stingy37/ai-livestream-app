#!/usr/bin/env bash
# US midterm market study: waits for a working YouTube login (scripts/youtube_auth.py), then measures every cell in
# us_midterms.json into cache5 (~100 quota units each) and prints the ranked table.
cd "$(dirname "$0")"
P=/home/andyshi2/.conda/envs/ai-livestream/bin/python
echo "=== waiting for a valid YouTube token $(date -u +%FT%TZ)"
until $P -c "import sys; sys.path.insert(0, '../../src'); from broadcast import youtube; youtube.service()" 2>/dev/null; do sleep 60; done
echo "=== measuring $(date -u +%FT%TZ)"
$P measure.py us_midterms.json --cache cache5 2>&1 | grep -v Warning | cut -c1-200
echo "=== table $(date -u +%FT%TZ)"
$P analyze.py --caches cache5 2>&1 | cut -c1-200
echo "=== done $(date -u +%FT%TZ)"

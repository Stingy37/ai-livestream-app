# Typhoon Champi pipeline — how it runs

Everything heavy runs on the ICRN machine; the EC2 instance only serves the website and the
packages it pulls from S3. One command runs the whole thing for hours:

```bash
# put the Lumen keys in place first (one per line; the pool rotates through them)
printf 'KEY1\nKEY2\n' > secrets/lumen_keys.txt
bash scripts/run_livestream.sh                      # = scripts/entrypoint.sh
MAX_HOURS=8 SCENES=position,impacts bash scripts/run_livestream.sh   # overrides are env vars
touch .run/STOP                                      # stop cleanly after the current scene
```

Services it starts (idempotent): `scripts/vllm_start.sh` (Qwen3-8B fp8 + the dynamic-RAG LoRA
`model_weights/dynrag_lora_v5_step60`, served as `qwen3-8b` and `dynrag` on :8000) and
`scripts/searxng_start.sh` (SearXNG on :8888). The EC2 side is deployed once with
`bash ec2/deploy.sh` (see `ec2/README.md`).

## Stages (one process per scene per stage, `src/main.py`)

| stage | team code | reads | writes (run folder `output/runs/<RUN_ID>/scenes/<scene_id>/`) |
|---|---|---|---|
| sources | `scraper.WebScraper` (LangGraph: search ReAct ≤3 rounds → verify → experts) then `qc.WebsiteScorer` (Part A) | Scene | `sources.json` (full Trafilatura text), `scrape_report.json`, `qc_part_a.json`, `scored.json` |
| context | `rag.Retriever` (sentence split → e5-base-v2 → FAISS flat; one retrieval with the scene description) | accepted `ScoredDocument`s | `index/`, `context.json` |
| script | `qc.ScriptHarness` → `writer.ScriptWriter` (dynamic RAG on vLLM + LoRA, retrieves during `<think>`) → `qc.ScriptScorer` (Part B: within-source + disputed facts), ≤3 rounds | `RetrievedContext` | `script_attempts.json`, `script.json` |
| audio | `audio.AudioGenerator` (Kokoro-82M, GPU) | `ScriptOutcome` | `<scene_id>.wav`, `audio.json`, `bundle.json` |
| broadcast | `broadcast.PackageBuilder` + `broadcast.Publisher` → EC2 presigned PUT → S3 → EC2 activates | bundles | `packages/<package_id>/` |

Stage artifacts carry the generation number (`stage_state.json`), so a crashed run resumed with
the same `RUN_ID` reuses what finished and redoes the rest. A scene that fails a stage twice is
dropped from that generation; the previous version stays on air during a regeneration.

## On-air loop and cycle regeneration

`graph.BroadcastGraph.traversal()` walks the config's graph, expanding `cycles` (`repetitions`,
`repetitions_until_update`). The harness "plays" each scene for its clip duration (a virtual
clock; real playback is the website), and when a cycle reaches `repetitions_until_update`
iterations its scenes are regenerated in the background (stages 1–4 again) and a new package is
published at the next scene boundary. The website switches packages only between scenes.

## What QC Part B flags (`qc.ScriptScorer`)

1. **Within-source contradictions** of the script with itself (`qc/simple/script.py`, whole-read for ≤25 sentences).
2. **Unattributed disputed figures**: a sentence that restates a figure Part A flagged as disputed between
   sources, without naming the agency in that sentence or the two before it.
3. **Unsupported figures**: any number read on air that occurs in no source sentence of the scene's index
   (deterministic; clock times, years and 0–12 are ignored). This is what stops invented figures.

A draft passes when the count is ≤ `SCRIPT_SCORE_THRESHOLD` (default 0). Otherwise the flagged items (top 8,
de-duplicated) go back to the writer as feedback, up to `SCRIPT_MAX_ATTEMPTS` (3); then the draft with the
fewest flags is used and a warning is recorded in `script.json`.

## Dynamic-RAG guard rails (`writer/dynrag.py`)

Identical mechanics to the trained rollout (Search-R1 template, forced-open `<think>`, stops at `</search>`,
`</think>`, `</answer>`, inserted `<information>` blocks, think/answer token budgets) plus: the up-front
retrieval with the scene description is written as the first search; a self-written `<information>` is an
invalid action (dropped, a one-line note inserted, thinking closed after 2); a repeated query gets a one-line
note instead of the block again; thinking is closed after 3 repeats, 12 searches or 24 turns.

## Lumen key pool (`src/models/lumen.py`)

Keys come from `LUMEN_API_KEYS`, `LUMEN_API_KEY` and `secrets/lumen_keys.txt`. Requests
round-robin; 429 → cooldown (Retry-After) and the next key; `insufficient_quota` → benched an
hour; 401/403/404 → benched; 5xx/timeouts → short cooldown. If every key is down and
`LUMEN_LOCAL_FALLBACK=1`, the local Qwen3 (thinking off) answers so the pipeline keeps moving.
New keys dropped into the file are picked up by every process that starts afterwards (the next
stage or regeneration); no restart needed.

## Knobs

All in `scripts/run_livestream.sh` (documented inline) and `src/config_env.py`. The most useful:
`MAX_HOURS`, `MAX_WORKERS`, `SCRIPT_MAX_ATTEMPTS`, `SCRIPT_SCORE_THRESHOLD`,
`QC_MAX_REMOVED_FRACTION`, `STALE_HOURS`, `REACT_MAX_ROUNDS`, `PUBLISH`, `DRY_RUN`, `SCENES`.

## Where to look when something is off

- `.run/livestream/<RUN_ID>.log` — harness + main.py log; `.run/vllm/vllm.log`; `.run/searxng/searxng.log`
- `output/runs/<RUN_ID>/status.json` — what is on air, pending regenerations, current package
- `output/runs/<RUN_ID>/scenes/<id>/script_attempts.json` — every draft, its contradictions, the search trace
- EC2: `sudo journalctl -u weather-livestream -f`, `https://127.0.0.1:18443/api/v1/status` through the tunnel

## Live desk data (`src/desk`, the website's numbers)

Nothing on the page is typed in by hand any more: `desk.json` is rebuilt every `DESK_INTERVAL_S` (600 s)
by a thread inside the harness, or alone with `bash scripts/desk_update.sh` (`--loop`, `--no-publish`).
It is published with `POST /api/v1/desk` and the page polls `GET /live/desk.json`.

| section | source (parsed in `desk/sources.py`, no LLM) |
|---|---|
| center, forecast (+ 70 % circles) | JMA `bosai/typhoon/data/<TC>/specifications.json` (JTWC position if JMA is down) |
| past track | JTWC `<id>.tcw` 6-hourly fixes (1-min winds); JMA track without times as a fallback |
| agency table | JMA, PAGASA bulletin, CWA `TY_NEWS-Data.js` (public, no key), JTWC warning text |
| PAGASA wind signals | the bulletin's signal tables (raised levels + areas, highest possible signal) |
| ensemble | NCEP ens_tracker on NOMADS: newest GEFS and FNMOC run that tracks the storm, 12-hourly to 168 h |
| cpa | closest approach of every reference city to the JMA track (`desk/geo.py`) |
| warnings, impact text, headlines, extra ticker items | Lumen LLM over the agency texts + the latest run's scraped pages; every item must quote its source exactly, every number must be in the quote, and absence claims or words like "evacuation", "landfall", "signal" need the quote to say so too (`desk/text.py`) |

Storm ids are discovered (JMA `targetTc.json`, JTWC RSS) by the config's storm name, so the next storm
needs no code change (`DESK_STORM`, `DESK_JMA_TC`, `DESK_JTWC_ID` override). A section whose source
fails keeps its previous value and is listed in `stale`, with the error in `provenance`. An invalid
document is never written or published, and the EC2 server keeps serving the last good one whatever
its age (204 only if nothing was ever published). Local copies: `output/desk/desk.json`, `history/`,
`last_report.json` (dropped LLM items with the reason).

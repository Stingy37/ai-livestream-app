# Election night runbook: election-es / election-ja / election-zh (2026-11-03)

Everything runs on this ICRN box (36-core cgroup quota, H200 MIG slice with no NVENC, so encoding is libx264 on CPU).
EC2 is not used by the election streams: the page and its `live/*` are served from local disk by `scripts/web_preview.py`.
All commands run from `/home/andyshi2/ai-livestream-app`, with `PY=/home/andyshi2/.conda/envs/ai-livestream/bin/python`.

```
state feeds ──> output/election/live/<ST>.json ─┐
AP call stories (SearXNG) ─> call_candidates.json ─(human confirm)─> output/election/calls.json ─┤
                                                                       scripts/election_run.sh (writer + TTS)
                                                                         └> output/election/air/election-<lang>/
web_preview.py :8095  /s/election-<lang>/ = html/election-desk.html, live/* from that folder  <── Chromium (encoder)
                                                                       └> ffmpeg ─> YouTube RTMPS (key from the API)
```

## Timeline (UTC / ET / JST; Beijing and Taipei are UTC+8)

| UTC | ET | JST | what |
|---|---|---|---|
| 22:00 Tue | 17:00 | 07:00 Wed | start the back end (step 1-4 below) |
| 22:30 | 17:30 | 07:30 | broadcasts prepared and checked, local encoder test |
| **23:00** | 18:00 | 08:00 | **es live** |
| **23:30** | 18:30 | 08:30 | **ja and zh live** |
| 00:00 Wed | 19:00 | 09:00 | first poll closings (GA, KY, NH, SC, VA...): calls for those can start |
| 00:30 | 19:30 | 09:30 | **OH** last close: watch the Ohio `IsTest` flag flip and its first numbers |
| 01:00 | 20:00 | 10:00 | **ME** closes (no official count tonight); TX, KS, MI main closes (still preview: last close 21:00 ET) |
| 02:00 | 21:00 | 11:00 | **TX, KS, MI** last close: TX numbers on screen; KS and MI have no reachable feed |
| 06:00 | 01:00 | 15:00 | **AK** last close: AK files appear later (watch the AK line turn from NotPublished to ok) |
| 08:00-09:30 | 03:00-04:30 | 17:00-18:30 | stop (es ~08:00, ja ~08:00, zh ~09:00 per docs/ELECTION.md) |

## Start order

```bash
# 1. search (for the AP call monitor) and the state feeds
bash scripts/searxng_start.sh                          # idempotent; JSON API on 127.0.0.1:8890
bash scripts/election_feeds.sh                         # start (idempotent): ALL states every 120 s -> output/election/live/
bash scripts/election_feeds.sh status

# 2. the page server, in its own session (see "Risks": never let encoder.sh start it)
curl -sf -o /dev/null http://127.0.0.1:8095/ || setsid nohup bash scripts/web_preview.sh >>.run/web_preview.log 2>&1 </dev/null &

# 3. the writer/voice runners (another session's code; see scripts/election_run.sh)
bash scripts/election_run.sh start                     # es ja zh -> output/election/air/election-<lang>/

# 4. the AP call-candidate monitor (writes candidates only, never calls.json)
(cd src && setsid nohup $PY -m election.calls monitor >>../.run/election/calls.log 2>&1 </dev/null &)

# 5. YouTube broadcasts: dry run, then create (writes to YouTube; once per stream; re-running re-applies metadata)
$PY scripts/election_youtube.py                        # lint + plan, no API call
$PY scripts/election_youtube.py --create --lang es     # then --lang ja, --lang zh (or no --lang for all three)
cat .run/youtube/election_es.json                      # broadcast id, ingest stream id, checks (no key in it)

# 6. local encoder check (files only, no YouTube): 3 encoders x 30 s, then look at a frame of each
bash scripts/election_encoders.sh test 30

# 7. go live: one youtube_live.py per stream (binds the prepared broadcast, starts encoder.sh with the RTMPS URL)
ELECTION_PRIVACY=public bash scripts/election_encoders.sh start es        # 23:00 UTC
ELECTION_PRIVACY=public bash scripts/election_encoders.sh start ja zh     # 23:30 UTC (started 20 s apart)
```

`start` goes live within a minute (the broadcasts have auto-start), so run it at the go-live time, not earlier. It
refuses a language without `.run/youtube/election_<lang>.json`, and it requires `ELECTION_PRIVACY` to be set explicitly.
Single-stream equivalent of step 7, for reference:
`YOUTUBE_TITLE="<title>" EC2_STREAM_ID=election-ja $PY scripts/youtube_live.py --config saved_configs/election_ja.json --lang ja --stream election-ja --privacy public --hours 11 --refresh-min 0`.

## Health checks (every 10-15 min, and after each poll closing)

```bash
bash scripts/election_encoders.sh status      # per stream: youtube_live up, encoder up, page heartbeat age (< 30 s), package on air,
                                               #   last YouTube health line ("stream active, health good, broadcast live"), masked
bash scripts/election_run.sh status           # writer/voice runners and the package each stream has on air
bash scripts/election_feeds.sh status         # last cycle: one line per state (ok / NotPublished / TestData / SourceBlocked)
(cd src && $PY -m election.calls list)        # confirmed calls, new candidates, CONFLICT / DISAGREES / POSSIBLE RETRACTION
curl -s 'http://127.0.0.1:8890/search?q=test&format=json' | $PY -c 'import json,sys; print(json.load(sys.stdin)["unresponsive_engines"])'
top -b -n 1 | head -25                        # 3 streams used ~4.5 of 36 cores in the test
```

Look at what a stream is showing (displays: es `:373`, ja `:164`, zh `:386`; derived from the stream id by encoder.sh):

```bash
UDOCKER_CONTAINERS=~/.udocker/containers-persist ~/.local/bin/udocker run --nobanner -v /tmp:/tmp -v $PWD/output:/out yt-encoder \
  ffmpeg -v error -y -f x11grab -video_size 1920x1080 -i :164 -frames:v 1 /out/frame_ja.png
```

Data freshness: `output/election/live/TX.json` and `OH.json` carry `fetched_at`; after their closes it should be under
5 min old. A failed fetch keeps the last good file, so a stale `fetched_at` is the sign of trouble.

## What to watch

* **Ohio `IsTest` (00:30 UTC).** Until the flip, the feeds log says `OH: TestData` and no OH.json exists. The adapter
  refuses `IsTest="true"` or `"1"` and accepts `"false"`, `"0"` or a missing attribute; the date guard (2026-11-03) also
  applies, and the ETag change makes the next conditional GET fetch the new file. Expect the OH line to turn `ok` shortly
  after 7:30 pm ET. **Never run `election.feeds --allow-test` with `--out output/election/live/`**: it writes test numbers
  that are not flagged as test in the output, and the loop would then keep that file.
* **Texas.** Pinned to election id 53815 (`TX_ELECTION_ID`, skips discovery). Two requests per poll (~1.6 + ~4.2 MB),
  one poll per cycle; a cycle is 120 s of sleep plus the fetch time, so TX sees one poll every ~2.2-2.5 min (the SOS
  refreshes every 5 min). The loop cannot go below 120 s (`ELECTION_FEEDS_LOOP_S` is clamped).
* **KS, MI, ME.** Blocked from both ICRN and EC2 (see probes below). The loop asks each once, then backs off for
  15 min (`ELECTION_BLOCKED_RETRY_S=900`): one honest request per host per 15 min, never a bypass. Those scenes say there
  is no official count; if a line ever turns `ok`, check the numbers by hand before trusting them. MI saves any body it
  gets to `output/election/raw/MI/` and raises ParseError (no parser yet).
* **Alaska.** `AK: NotPublished` (the `/enr/26GENR/results/` CSV is 404) until the Division posts the general. After
  06:00 UTC watch for `ok`; `AK_CSV_URL` / `AK_PDF_URL` override discovery if the page lags.
* **AP calls.** The monitor is a helper, not the source of truth: also keep AP's results/race-call pages open in a normal
  browser. When `calls list` shows a candidate:
  1. open the URL; check it is a published story, it says AP declared/called the race (other outlets: explicitly AP),
     the state and the candidate match, it is the U.S. Senate general (not a primary, runoff, governor or House race), and
     note AP's time in ET;
  2. `(cd src && $PY -m election.calls confirm TX paxton --url <url> --outlet apnews.com --at "10:42 PM ET")`
     (refused before the state's last poll close, for a key not on the 2026 ballot, or when the outlet is not the URL's site);
  3. check the next pass of that scene shows "Race call: The Associated Press (via apnews.com), 10:42 PM ET".
  A `CONFLICT` (two winners for one state), `DISAGREES WITH A CONFIRMED CALL` or `POSSIBLE RETRACTION` line means: read
  the reports, and if AP withdrew or the reports are ambiguous, retract at once (rule 7):
  `(cd src && $PY -m election.calls retract TX --reason "AP retracted its call")`, then make sure it is said on air.
* **Search engines.** At 16:00 UTC SearXNG already reported DuckDuckGo (CAPTCHA), Google and Qwant (access denied) as
  unresponsive; only Brave, Bing and Yahoo answered. The monitor keeps its load low (3 global queries + the featured
  states from 30 min before their close + 4 rotating others per 5-min cycle, 6 s apart). If `searx_ok` is false in
  `call_candidates.json`, the monitor is blind: rely on the browser.
* **Encoders.** Heartbeat age climbing past 30 s, or a frame grab showing a frozen or half-drawn page: `bash
  scripts/election_encoders.sh reload <lang>` (kills that encoder; youtube_live.py restarts it within 60 s; YouTube keeps
  the broadcast through a short gap).

## Stop

```bash
bash scripts/election_encoders.sh stop es          # ends that broadcast (touch .run/STOP_YOUTUBE_election-es) and its encoder
bash scripts/election_encoders.sh stop             # all three
bash scripts/election_run.sh stop
bash scripts/election_feeds.sh stop                # = touch .run/STOP_ELECTION_FEEDS (exits within ~5 s)
touch .run/STOP_ELECTION_CALLS                     # call monitor exits within ~5 s
bash scripts/searxng_stop.sh
```

youtube_live.py also ends each broadcast by itself after `ELECTION_HOURS` (11 h).

## Test results (2026-11-03, 15:45-16:15 UTC)

**Local serving** (`scripts/web_preview.py`, curl against a test instance on port 8197 with a scratch air folder):
`/s/election-ja/` serves html/election-desk.html with the query string kept (`/s/election-ja?x` redirects to
`/s/election-ja/?x`); `live/current.json` and `live/desk.json` give 204 + `Cache-Control: no-store` while missing and 200 +
no-store once written; a scene wav gives 200 (`Accept-Ranges: bytes`), 206 for `bytes=0-99`, `bytes=100-` and `bytes=-10`,
and 416 past the end; `..`, `%2e%2e`, encoded slashes, symlinks out of the folder, nested paths and missing files are 404;
`POST live/playback` writes `playback.json` atomically (400 for non-JSON or a non-object). Other streams are unchanged
(`/s/japan/` -> champi desk, `/s/india-te/` -> india desk, their `live/*` still proxied to EC2), and so are
`election/geo/*` and the other site files.

**Three encoders side by side** (1080p30, libx264 veryfast 4500k, 60 s files in `output/election_encoder_test/`,
pages from a test preview whose `election-<lang>` folders pointed at the runner's `sample-<lang>` packages):

| run | page | frames / 60 s | gaps > 50 ms | audio (mean / max) | video bitrate | CPU, whole box |
|---|---|---|---|---|---|---|
| 1 (16:06) | desk.js mid-edit: stage never laid out (fit() not reached), no audio | 1800 each | 0 | silent | 0.54 Mb/s | ~2.7 cores |
| 2 (16:12) | renders correctly, narration playing (zh frame checked) | 1800 each | 0 | -27/-3, -23/-3, -22/-4 dB | 2.5-3.1 Mb/s | **4.3-5.4 cores of 36** |

So ffmpeg keeps 30.0 fps at speed 1.0x (real-time x11grab, no dropped or duplicated frames) for all three at once.
Per process (top, 5-s samples): the three ffmpegs together 1.3-2.3 cores (~0.5-0.75 each), the three Chromiums
1.1-2.0 cores; start-up of the browsers is ~1.6-1.9 cores for the first ~15 s. The whole-box figure includes everything
else running (a 15-s burst to 11-16 cores in run 1 was other work: the encoders stayed at ~2 cores then). Headroom is
roughly 7x on CPU. `scripts/election_encoders.sh test 15 ja` was also run end to end (isolated preview, 15 s file,
~3 Mb/s). Run 1 is a reminder to freeze the page before 22:30 and to grab a frame of each stream after going live.

**Feeds loop** (`scripts/election_feeds.sh`, one live cycle at 15:50 UTC): TX ok (zero file, 254 counties, 0/9,900
precincts); AK NotPublished; OH TestData (`IsTest="true"`); KS, ME, MI SourceBlocked, then backed off for 900 s. The
pid file keeps a second start from launching a second loop; `stop` (touch the STOP file) ended it in under 7 s. Tests:
`tests/election/test_feeds.py` (24 passed, including the IsTest flip and the blocked back-off).

**Probes from EC2** (egress 184.194.177.117, 15:51 UTC, one request each, no redirects followed, UA
`election-results-desk/0.1 (independent livestream)`):

| state | URL | answer |
|---|---|---|
| KS | https://ent.sos.ks.gov/national.html | HTTP/2 403, `cf-mitigated: challenge`, Cloudflare "I'm Under Attack" JS challenge. The 403 body (659 KB) carries the page title next to the challenge script; it is served as a challenge, so it is not used. |
| MI | https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-3-2026 | HTTP 403, `Cf-Mitigated: challenge`, "Just a moment..." managed challenge |
| ME | https://www.maine.gov/sos/elections-voting/election-results-data/election-results-2026 | HTTP/2 403, CloudFront "Request blocked" |

All three are challenged or blocked from EC2 exactly as from ICRN, so no EC2 fetch option or relay was added and
nothing was changed on the server. The remaining honest routes are the ones in feeds.md: ask the KS SOS / MI Bureau of
Elections to allowlist the desk, or county offices' official pages.

**AP call matcher** (`tests/election/test_calls.py`, 92 passed): the nine 2024 AP race-call headlines as SearXNG returns
them (truncated, e.g. "AP Race Call: Democrat Elissa Slotkin wins election to U.S ..." with
`/article/race-call-slotkin-wins-michigan-senate-<hash>`), full forms, AP news headlines ("Democrat Ruben Gallego wins
Arizona US Senate race against ...", "Republican Tim Sheehy defeats Jon Tester to win Montana US Senate seat"), "Why AP
called the <State> Senate race for <X>", other outlets ("AP calls Pennsylvania's U.S. Senate race for Dave McCormick",
"... the Associated Press has called the Pa. Senate race for ..."), a syndicated truncated title resolved from the lede,
and 2026 forms for every featured candidate. Rejected: governor and House race calls (from the URL), primaries,
nominations, runoffs, the 2026 Paxton runoff live blog, opinion, "How/Can/If" headlines, endorsements, debates,
forecasts, "leads", wrong party, title/URL disagreement, names not on the 2026 ballot (Cornyn), "Sullivan" alone (two
Sullivans in Alaska), "too close to call" / "has not called" / "yet to call", DDHQ and network projections, and stories
dated before the state's polls closed. "Democrat Jacky Rosen reelected to U.S. Senate from Nevada" is deliberately not
taken (no "wins"); AP's own "AP Race Call: ... wins ..." story for the same race is.

## YouTube: exact commands and what is missing

Commands (steps 5 and 7 above): `scripts/election_youtube.py` prepares each broadcast with `src/broadcast/youtube.py`
and `saved_configs/election_<lang>.json` (`youtube` section): its own reusable 1080p30 ingest stream
`encoder-election_<lang>` (= one stream key per language, the same one youtube_live.py binds), a broadcast scheduled for
23:00 / 23:30 / 23:30 UTC, unlisted, `selfDeclaredMadeForKids=false`, auto-start, DVR; then `videos.update` with
categoryId 25 (News & Politics), tags, languages, and `status.containsSyntheticMedia=true`; it reads the video back and
prints the checks (synthetic, not made for kids, category 25, thumbnail). Nothing has been created; only the dry run was run.

Missing or wrong for election use:
1. **youtube_live.py's own prepare path is typhoon-specific.** `metadata()` would title and tag the broadcast as a
   typhoon desk (tags "typhoon", "typhoon live"; there is no `YOUTUBE_TAGS` override), and `youtube_thumbnail.render()`
   would draw the typhoon hero thumbnail through `/s/election-<lang>/thumb-hero.html`. Hence the separate prep script, and
   `election_encoders.sh start` refuses a language that has no prepared broadcast. It passes `--refresh-min 0` and
   `YOUTUBE_TITLE` so the hourly typhoon thumbnail/title refresh never runs.
2. **No election thumbnail file yet.** `html/thumb-election.html` and `saved_configs/thumb_election_<lang>.json` exist,
   but nothing renders them to `output/youtube/thumb_election_<lang>.jpg` (1280x720 JPEG under 2 MB; `set_thumbnail`
   uploads as image/jpeg). Without it the broadcast gets YouTube's default frame; the prep script reports
   `thumbnail: False` and can be re-run after the file exists.
3. **Chinese language code.** youtube_live.py maps `zh` to `zh-TW` (Traditional). The election zh stream is Simplified, so
   the config uses `zh-Hans`; this code is not verified against `i18nLanguages.list`. If `videos.update` rejects it, use
   `zh-CN` and re-run `--create --lang zh` (it reuses the broadcast and re-applies the metadata).
4. **Defaults:** `--hours 6` would end the broadcasts at 05:00-05:30 UTC, before AK reports; the script passes 11.
5. **The titles, descriptions and tags in `saved_configs/election_<lang>.json` are drafts.** They carry the legal.md
   s6b disclosure verbatim, "unofficial", the AP-only call rule, the source list and a corrections note (rule 46), and pass
   the prep script's lint (length, no "official", no network/wire names, no winner words), but a native speaker should read them.
6. **Logs can hold the key.** ffmpeg error lines may print the RTMPS URL with the key in
   `.run/encoder/election-<lang>/ffmpeg.log`, and all three youtube_live.py processes append their encoder output to
   the shared `.run/encoder/youtube_encoder.log`. `election_encoders.sh status` masks it; never paste those files.
7. **Privacy flip while live** is not supported by youtube_live.py (it only sets privacy at start). To preview unlisted
   and then go public, restart with the new `ELECTION_PRIVACY` (the broadcast is reused), or call `youtube.set_privacy`.
8. Quota: about 300 units per stream to prepare, 2 units per 10-min health check; well under the 10,000/day default.

## Risks

* **The page.** It was mid-edit at 16:06 and drew only its background; at 16:12 it was fine. Freeze
  `html/election-desk.html` / `election/desk.js` before 22:30 and grab a frame of each stream after going live.
* **The preview server is a single point of failure** for all three streams. Start it on its own (step 2): if
  `encoder.sh` starts it, it lives in that encoder's process group, and stopping or reloading that encoder would kill the
  page server for all three. `election_encoders.sh` starts it with `setsid` when it is down.
* **KS, MI, ME have no official count tonight**, from any network we control; those scenes must keep saying so. AK
  numbers come only after 06:00 UTC, possibly much later.
* **Texas** could start challenging (its old portal is behind Cloudflare). The adapter would report `SourceBlocked`, keep
  the last good file and back off; the scene then shows stale numbers with their "as of" time.
* **Ohio's first real file** has never been seen (no real-number fixture exists); watch the first `ok` line and compare
  the statewide total with the SOS page by hand.
* **AP calls depend on search engines** that are already partly rate-limited; a human watching AP directly is the real
  safeguard. The monitor never writes calls.json; a wrong confirm is a human error, which `retract` fixes at once. The
  writer must also say the retraction on air (rule 7); check that `election_run.sh` does.
* **CPU** is not a risk (about 4.5 of 36 cores for three streams); the other workloads on this box are (TTS/LLM for the
  runners). Check `top` after all three are live.

## Operator watch (added by the main session)

`python scripts/election_watch.py --live es,ja,zh` blocks until something needs the operator and prints one line per
event: `CALLS <ST> <key> | headline | url` (review the AP story, then `cd src && python -m election.calls confirm ...`),
`RUNNER`/`STALE`/`ENCODER` (restart with election_run.sh / election_encoders.sh), `FEED` (TX/OH/AK parse errors),
or `HEARTBEAT` after 25 min. Run it in the background and re-arm it after each event.

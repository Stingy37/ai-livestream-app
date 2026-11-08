# US midterms 2026 election-night streams (es / ja / zh)

Election day: Tue 2026-11-03. ET = UTC-5 (DST ended Nov 1). JST = ET+14, Taiwan = ET+13.
Three streams, same data and visual system, each narrated natively in its language:

| stream | go live | peak (2022 analog) | hold to |
|---|---|---|---|
| ja | 23:30 UTC Tue (18:30 ET / 08:30 JST Wed) | 11:00-13:00 JST | ~08:00 UTC Wed (17:00 JST) |
| es | 23:00 UTC Tue (18:00 ET) | 20:00-21:00 ET | ~08:00 UTC Wed (03:00 ET) |
| zh | 23:30 UTC Tue (18:30 ET / 07:30 Taiwan Wed) | 22:00-03:00 ET | ~09:00 UTC Wed |

## Scenes (one playlist per stream)

1. `national`: whole-country Senate map, balance of power, key-race status, poll-closing schedule, analysis.
2. One scene per state, in this order: **TX, AK, KS, ME, OH, MI** (each state's US Senate race; OH is the special
   election for Vance's former seat). Each state scene covers ONLY:
   1. senators (the two current senators, the seat that is up)
   2. votes left (counted so far vs the 2022 midterm total, precincts reporting where the state publishes it)
   3. past election data (2024 presidential result, statewide and by county; the seat's previous election)
   4. candidate basic info (background, positions, attributed to the candidate's own statements / record)
   5. current votes (official count)
   6. breakdown by county (AK: state house district; ME: county aggregated from towns)

Phase per state, from the clock and the data: `preview` (polls open: 1, 3, 4 + poll-closing countdown),
`counting` (all items), `projected` (an AP projection relayed with attribution, never our own call).

## Script ↔ screen alignment (the core difference from the weather desks)

The writer returns **beats**, not prose. A beat is one visual state plus the sentences spoken over it; a sentence may
carry a `focus` (a county, a candidate, a senator) that the page highlights while that sentence plays.

```json
{"scene": "TX", "phase": "counting", "beats": [
  {"visual": "results", "lines": [{"text": "...", "focus": null}]},
  {"visual": "counties", "lines": [{"text": "...", "focus": "48201"}, {"text": "...", "focus": "48113"}]}
]}
```

Every sentence is synthesized separately, so the package knows each sentence's exact start and end time. The manifest
carries the beat timeline and the **data snapshot** the script was written from; the page renders that snapshot (not
newer data) while the scene plays, so what is said and what is shown can never disagree. Newer numbers appear only in
the ticker and on the next pass of the scene.

Visuals (enumerated, the writer may only use these):
- national: `nat_map`, `nat_balance`, `nat_races`, `nat_schedule`
- state: `st_intro`, `st_senators`, `st_candidates`, `st_results`, `st_counties`, `st_votes_left`, `st_history`,
  `st_poll_close`

## Shared data schemas

### Live results, one file per state race: `output/election/live/<ST>.json`

```json
{
  "state": "TX", "race": "senate", "unit_type": "county",
  "source": "Texas Secretary of State", "source_url": "https://...",
  "fetched_at": "2026-11-04T01:23:45Z", "source_updated_at": "2026-11-04T01:20:00Z" ,
  "candidates": [{"key": "cornyn", "name": "John Cornyn", "party": "REP", "votes": 123456}],
  "total_votes": 234567,
  "precincts": {"reporting": 1234, "total": 9000},
  "units": [{"id": "48201", "name": "Harris", "votes": {"cornyn": 1234}, "total": 2345,
             "precincts": {"reporting": 10, "total": 1100}}]
}
```
`precincts` is null where the source does not publish it. Unit ids: 5-digit county FIPS; Alaska `AK-HD01`..`AK-HD40`.

### Baseline, one file per state: `data/election/baseline/<ST>.json`

```json
{
  "state": "TX", "name": "Texas", "fips": "48", "unit_type": "county",
  "statewide": {
    "pres2024": {"dem": 0, "rep": 0, "other": 0, "total": 0, "dem_name": "Kamala Harris", "rep_name": "Donald Trump"},
    "sen_prev": {"year": 2020, "dem": 0, "rep": 0, "other": 0, "total": 0, "dem_name": "...", "rep_name": "...", "winner": "REP"},
    "turnout2022": 0
  },
  "units": [{"id": "48201", "name": "Harris", "pres2024": {"dem": 0, "rep": 0, "other": 0, "total": 0},
             "sen_prev": {"dem": 0, "rep": 0, "other": 0, "total": 0}, "turnout2022": 0}],
  "sources": [{"what": "pres2024", "publisher": "Texas Secretary of State", "url": "https://..."}]
}
```
Geometry (page assets): `html/election/geo/us-states.json`, `html/election/geo/<ST>.json` (GeoJSON, simplified,
`properties.id` = the unit id above, `properties.name`).

### Races and candidates: `data/election/races.json`

All 35 Senate races of 2026 (holdovers too, for the national map), and for the six featured states full candidate
cards. See `research/election/candidates.md` for sourcing rules.

## Rules (see `research/election/legal.md`)

- Never call a race. "Leads" from the official count; a projection only as "AP projects ..." relayed from a news
  report, with attribution on screen and in the sentence.
- No exit polls, no network graphics, logos or proprietary names. Official counts and public-domain data only.
- AI-voice disclosure on screen in each language and `containsSyntheticMedia` on the broadcast.
- Neutral: equal fields per candidate, positions attributed to the candidate, no characterisations, no predictions.

## Corrections after research (2026-11-03)

- Wording: AP *declares* winners. Never "projects". On screen: "Race call: The Associated Press (via <outlet>), <time> ET".
- Chinese stream is **Simplified** (zh-Hans), Mandarin voice.
- Votes left is only "counted so far = X% of the 2022 midterm total" (legal rule 13); no expected-vote models.
- Last poll closings (ET): OH 19:30, ME 20:00, TX 21:00 (main 20:00), KS 21:00 (main 20:00), MI 21:00 (main 20:00),
  AK 01:00 Wed. Nothing about a state's count before its LAST close (rule 27).
- No official election-night count reachable for KS, MI (Cloudflare challenge, not bypassed) and ME (none published):
  those scenes say so and stay on candidates / senators / history until an official count appears.

## Page contract (`html/election-desk.html`)

Streams: `election-es`, `election-ja`, `election-zh`. The page is served by `scripts/web_preview.py` at
`/s/<stream>/?autoplay=1&lang=<es|ja|zh>`; its relative `live/` URLs are served from local disk,
`output/election/air/<stream>/` (no EC2 round trip):

- `live/current.json` — the package manifest below (204 while none). Polled every 5 s.
- `live/<package_id>/<file>.wav` — scene audio.
- `live/desk.json` — the newest data for the persistent chrome (ticker, balance bar, race strip, countdown). Polled 30 s.

### Manifest

```json
{
  "package_id": "pkg-20261104T011500Z-ab12cd", "created_at": "...", "lang": "ja", "is_test": false,
  "playlist": ["national-7", "TX-7", "AK-7", "KS-7", "ME-7", "OH-7", "MI-7"],
  "scenes": [{
    "scene_id": "TX-7", "key": "TX", "kind": "state", "phase": "preview|counting|declared",
    "audio": {"path": "TX-7.wav", "duration": 131.2},
    "beats": [{"visual": "st_results", "start": 0.0, "end": 14.2,
               "lines": [{"text": "...", "start": 0.0, "end": 5.1, "speaker": "A", "focus": "paxton"}]}],
    "snapshot": { /* state or national snapshot, below */ },
    "generated_at": "..."
  }]
}
```

Times are seconds from the start of the scene's audio. The page owns the scene-to-scene transition (it may hold the
audio start until its stinger has covered the screen, <= 1.2 s), then switches visuals exactly at `beats[i].start`
and applies `lines[j].focus` exactly at `lines[j].start` (from `audio.currentTime`, checked every animation frame).
Speaker "A" is the anchor, "B" the analyst at the map; the page may show a small speaker label.

### State snapshot (`kind: "state"`) — everything already localised for the stream's language

```json
{
  "state": "TX", "state_name": "テキサス州", "race_label": "上院選", "special": false, "rcv": false,
  "phase": "counting",
  "poll_close": {"main_et": "2026-11-03T20:00:00-05:00", "last_et": "2026-11-03T21:00:00-05:00"},
  "as_of": "2026-11-04T02:10:00Z", "source": "Texas Secretary of State", "official": true,
  "results_available": true,
  "candidates": [{"key": "paxton", "name": "ケン・パクストン", "short": "パクストン", "party": "REP",
                  "party_label": "共和党", "incumbent": false, "votes": 123456, "pct": 52.1, "ahead_by": 12345}],
  "total_votes": 234567,
  "precincts": {"reporting": 1234, "total": 9900},
  "counted_vs_2022": {"counted": 234567, "total2022": 8102908, "pct": 2.9},
  "units": {"type": "county", "geo": "election/geo/TX.json",
            "rows": [{"id": "48201", "name": "ハリス郡", "leader": "talarico", "margin_pts": 12.3, "total": 123,
                      "counted_vs_2022_pct": 34.0, "votes": {"paxton": 1, "talarico": 2}}]},
  "callouts": ["48201", "48113", "48029", "48453", "48439"],
  "history": {"pres2024": {"dem_name": "ハリス", "rep_name": "トランプ", "dem": 4835250, "rep": 6393597,
                           "dem_pct": 42.5, "rep_pct": 56.1, "total": 11388674},
              "sen_prev": {"year": 2020, "dem_name": "...", "rep_name": "...", "dem_pct": 43.9, "rep_pct": 53.5},
              "units": {"48201": {"winner": "DEM", "margin_pts": 2.6, "pres2024": {"dem_pct": 50.4, "rep_pct": 47.8}}}},
  "senators": [{"name": "ジョン・コーニン", "party": "REP", "party_label": "共和党", "since": 2002,
                "up": true, "running": false, "note": "予備選の決選投票で敗退"}],
  "cards": [{"key": "paxton", "name": "...", "party": "REP", "party_label": "共和党", "incumbent": false,
             "role": "テキサス州司法長官", "age": 63, "facts": ["...", "...", "..."], "positions": ["...", "...", "...", "..."]}],
  "call": null,
  "rcv_note": null
}
```

`call` (only from an AP declaration relayed in a news report): `{"key": "paxton", "text": "<localised call
sentence>", "credit": "Race call: The Associated Press (via apnews.com), 10:42 PM ET"}`. The page never draws a
check mark or a winner badge for anything else. `results_available: false` (polls not closed, or no official
count) → the results/counties/votes-left visuals show the preview state ("Polls close 9:00 PM ET" /
"No official count published yet") and the county map shows 2024.

### National snapshot (`kind: "national"`)

```json
{
  "balance": {"majority": 51, "holdover": {"REP": 31, "DEM": 32, "IND": 2}, "declared": {"REP": 0, "DEM": 0, "IND": 0},
              "undecided": 35},
  "races": [{"state": "TX", "state_name": "...", "status": "polls_open|polls_closed|counting|declared",
             "incumbent_party": "REP", "declared": null, "featured": true, "poll_close_last_et": "...",
             "leader": null}],
  "schedule": [{"et": "2026-11-03T19:00:00-05:00", "states": ["GA", "KY", "NH", "SC", "VA"]}],
  "as_of": "..."
}
```
`leader` is filled only for featured states with an official count after their last close: `{"party": "REP",
"short": "...", "pct": 52.1}`. The national map colours: holdover-only states grey, races by status
(open = light grey, closed/counting = neutral highlight, declared = party colour), featured states outlined.

### Visual ids (the writer may only use these; the page must implement all)

national: `nat_map` (focus: a state code), `nat_balance`, `nat_races` (focus: state), `nat_schedule`
state: `st_intro`, `st_senators` (focus: senator index "0"/"1"), `st_candidates` (focus: candidate key),
`st_results` (focus: candidate key), `st_counties` (focus: unit id → zoom + callout box), `st_votes_left`
(focus: unit id), `st_history` (focus: unit id), `st_poll_close`

### desk.json (persistent chrome; may be newer than the scene snapshot)

```json
{"as_of": "...", "lang": "ja", "national": { /* national snapshot */ },
 "strip": [{"state": "TX", "label": "TX 上院", "status": "counting", "rows": [{"short": "パクストン", "party": "REP", "pct": 52.1}],
            "counted_vs_2022_pct": 2.9}],
 "next_close": {"et": "2026-11-03T21:00:00-05:00", "states": ["TX", "KS", "MI"]},
 "ticker": ["...", "..."]}
```

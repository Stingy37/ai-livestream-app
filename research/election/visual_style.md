# Election-night graphics: visual style spec (US networks + es/ja/zh desks)

Target: one HTML page, 1920x1080, Chromium -> ffmpeg. Scenes as in `docs/ELECTION.md`.
Reference set (local only, gitignored): 12 sections in `research/election/clips/`, 42 stills in
`research/election/frames/` (index in section 9). All px values are in 1920x1080 space (720p sources x1.5).
"cap" = measured cap height in px. Font sizes below are already converted from cap using each font's
cap/em ratio (Oswald 0.815, Roboto Condensed 0.711, Figtree 0.705, Fjalla One 0.835).
Hexes marked (f) were sampled off a filmed video wall and are colour-cast; treat as approximate.

## 1. Canvas, grid, layers

| item | value | measured basis |
|---|---|---|
| side margins (safe-x) | 80 px (content 80..1840) | CNN 71/90, NBC 82, ABC 83, CBS 62, Fox 105 |
| top margin | 48 px | full-screen boards start 14-60 px |
| bottom edge of US-style bars | y 1030 (50 px margin) | CNN 1050-1060, Fox 1030, CBS 1048, NBC 998 |
| full-bleed band (ja/zh crawl, disclosure) | y 1030..1080, x 0..1920 | TBS crawl band 925-1080, FTV/TVBS bars to 1080 |
| columns | 12 cols, 20 px gutters, col = 128.3 px | |
| data area (no headline bar) | y 48..856 | |
| data area (headline bar up) | y 48..748 | CNN board ends at y 760 when 3-tier lower third is up |

Layer order (z): background -> scene panels -> map -> callouts -> headline bar (HB) -> bottom bar (BB) -> bug/clock
-> crawl/disclosure -> stinger overlay. BB, bug, clock and disclosure are persistent on every scene (Fox/CNN
keep their bar over full-screen boards; ABC hides it - we do not).

## 2. Colour

Sampled per network (direct renders unless (f)):

| role | CNN | Fox | NBC | ABC | CBS | Univision/Telemundo | TBS (ja) | FTV/TVBS (zh) |
|---|---|---|---|---|---|---|---|---|
| Dem block | #0B5AA6 strip, #0D66BE board, #2BA5E5 wall | #1549A3 | #0B70E4 (f), text #188ED7 | #0950B2, navy #08256E | #0C64A4 | blue similar (f) | #0F2981 | #0644A9 / #4462DB |
| Rep block | #AD0004 strip, #B00005 board, #CC142E wall | #95000B | #D43B3E (f), text #B23452; uncounted county #6E84AE (f) | #B40002, dark #680001 | #B60309 / #C90007 | red similar (f) | #AC182B | #A4013A / #C61721 |
| panel base | wall navy #1B1948, board red #B20007 | virtual set | light #DEDEE1 | header grey #454545 | white #E9EBEF | navy #141E59 (f) | beige #E3D1C1 on purple #600AC5..#7F00D7 | grey #4D4D4D header |
| strip grey | #E4E4E4 | #E7E9EF | #DEDEE1 | - | #E9EBEF | - | - | - |
| breaking/alert | tab #D30E23 | banner #8B0A24 -> #5A0616 | bar #A00008 | LIVE red | - | - | - | title bar yellow #F1FF0D |
| accent | meter green #4B9136 | lemon #F2F629 | yellow #F1DD20 / #EDC507 | - | toss-up purple | gold #C9A227 (f) | - | swing yellow #EED51D |

Our tokens (network-average, neutral; party colours never used as page chrome):

```css
:root{
  --dem-900:#08256E; --dem-700:#0B5AA6; --dem-500:#1F6FD1; --dem-300:#2BA5E5; --dem-ramp:#0A3C99,#1F6FD1,#7FB0EE,#C6DBF7;
  --rep-900:#680001; --rep-700:#AD0004; --rep-500:#CC142E; --rep-300:#F07E86; --rep-ramp:#A3000D,#D0142E,#F07E86,#F8C9CC;
  --ind-700:#5B5F6B;  /* independents/others: neutral slate, never green/purple */
  --navy-950:#0E1124; --navy-900:#1B1948; --navy-800:#232657; --navy-700:#2E3270; /* CNN wall family */
  --plate:#FEFCFC; --strip:#E4E4E4; --ink:#111111; --ink-2:#4A4A4A; --mute:#8C8C8C;
  --alert:#A00008; --tab:#D30E23; --live:#D30E23;
  --yellow:#F1DD20; --gold:#E2B227; --meter:#4B9136; --meter-off:#2A2F45;
  --map-norace:#3A4256; --map-pending:#5B6475; --map-closed:#6B6F76; --map-line:#0E1222; --map-nodata:#4A5266;
}
```

County margin ramp (ABC 4-step + CNN/NBC conventions): leader margin >=20 pts -> ramp[0]; 10-20 -> [1];
5-10 -> [2]; <5 -> [3]; exact tie -> #9AA3B5; zero votes counted -> `--map-nodata` (NBC greys uncounted
counties). Use the same ramp for 2024 history maps.

## 3. Typography

| role | font (Google) | weight | why (width ratio vs network, 1.00 = exact) |
|---|---|---|---|
| condensed caps: headlines, state names, HB, flipper headers | Oswald | 600 (700 bold word / 400 light word) | CNN headline 1.08, NBC state 1.08; alt Fjalla One 0.97-1.04 |
| all numerals, race-strip names | Roboto Condensed | 700 / 800 | CNN strip name 1.02, Fox banner 0.98; digits tabular by default (no roll-up jitter) |
| title-case & label sans (wall titles, first names, cards) | Figtree | 300/400/800 | ABC surname 1.03 (Montserrat is 1.15, too wide) |
| ja | BIZ UDPGothic 700 (labels, crawl), Noto Sans JP 900 (headers) | | TBS-style UD gothic |
| zh-Hant | Noto Sans TC 900 (title bar), 700 (labels) | | FTV/TVBS heavy hei |

Never use Oswald for changing numbers (no `tnum` in the variable build). Set `font-variant-numeric: tabular-nums`
on every number; `font-kerning: normal`; letter-spacing 0 for display caps, +0.04em for labels under 20 px.

Measured caps -> our sizes:

| element (source) | cap | our font-size |
|---|---|---|
| HB headline (CNN 57, NBC 59) | 57 | Oswald 600 70 px |
| breaking tab "BREAKING NEWS" (CNN) | 35 | Figtree 800 50 px (we use 40 px: shorter tab) |
| BB header "U.S. SENATE" / state (CNN22) | 38 | Oswald 600 46 px |
| BB race type "SENATE" small caps (CNN22) | 26 | Oswald 400 32 px |
| BB name / votes / % (CNN22: 39 / 40 / 36) | 39 | Roboto Cond 700 55 px / 56 px / 51 px |
| BB balance numerals (CNN22) | 62 | Roboto Cond 800 87 px |
| BB tile label "DEMOCRATS" | 13 | Roboto Cond 700 18 px +0.04em |
| tiny caption "NEEDED TO CONTROL" | 9 | Roboto Cond 700 13 px +0.06em |
| clock "2:32 AM PT" / bug footer | 18 / 20 | Roboto Cond 600 26 px / 28 px |
| board state name "WISCONSIN" (CNN board) | 105 | Oswald 700 129 px |
| board race tag "PRESIDENT" | 34 | Oswald 600 42 px |
| board first / LAST name (CNN, two lines, 7 px gap) | 35 / 45 | Oswald 500 43 px / Oswald 700 55 px |
| board lead label "31,167 AHEAD" (grey) | 25 | Roboto Cond 600 35 px #8C8C8C |
| board votes | 50 | Roboto Cond 700 70 px |
| board % (sign 0.6x, superscript) | 80 | Roboto Cond 800 112 px |
| card race "GOVERNOR" / state (ABC) | 45 / 35 | Figtree 800 64 px / 50 px |
| card first / LAST (ABC) | 34 / 45 | Figtree 300 48 px / Figtree 800 64 px |
| card % / votes (ABC) | 95 / 42 | Figtree 800 135 px / Figtree 500 60 px |
| wall title "Milwaukee County" + "2024" (CNN) | ~60 | Figtree 800 + Figtree 300, same size 85 px |
| countdown digits (NBC) | 78-80 | Roboto Cond 800 110 px |
| countdown state "PENNSYLVANIA POLLS CLOSE" | 65 | Oswald 700 + Oswald 400 80 px |
| votes-left numbers / labels (NBC) | 53-58 / 30 | Roboto Cond 800 76 px / Oswald 500 37 px |
| ja crawl glyph (TBS) | 56 glyph | BIZ UDPGothic 700 64 px |
| zh title bar glyph (FTV) | ~80 glyph | Noto Sans TC 900 84 px |

Spacing rules (all networks):
- Caps text fills 0.75-0.83 of its row: CNN strip row 47 px holds cap 39; never pad more than 8 px above/below.
- Two-line names: first name cap = 0.75x last-name cap, gap 0.15x last cap, line-height 0.95.
- Left text inset inside a coloured block: 0.6x cap (CNN headline 33 px at cap 57; NBC 58 px). Numbers sit flush
  right with 0.4x cap inset; `%` hangs at 0.55-0.6x size, top-aligned (CNN, ABC) or baseline (Fox).
- Max chars at full size: HB headline 44 (CNN 49 fits 1450 px; NBC 44 in 1304 px); strip surname 11;
  card surname 12; first name 12; ja crawl unlimited; zh title bar 18 chars.
- Fitting order for long names: (1) surname only in strips (all networks), (2) `transform: scaleX()` down to 0.80
  (Fox squeezes "GLUESENKAMP PEREZ*"), (3) font-size steps of -6% down to 80%, (4) a short form from data. Never wrap
  in a strip, never ellipsis.
- Everything in strips/HB is ALL CAPS; title case only on the wall title/panel (CNN "Milwaukee County 2024",
  "President", "Est. Reporting"). Party shown as a letter chip D/R/I (CNN tag on photo, Fox square, CBS corner).
- Incumbent: asterisk after surname (Fox "CASEY*") in strips; "INCUMBENT" tag on cards (CNN).
- Thousands separators always; US style "1,676,450" and "49.7%" also on Spanish networks (Telemundo "1,320",
  "49.7%"). One decimal for %, TBS uses two decimals with decimals at 70% size ("39.94%").
- Density: a full-screen board shows <= 4 candidate rows (networks show 2); lower-third zone holds <= 3 tiers
  (tab, headline, bar); one county panel shows 2 candidate rows + 1 context line.

## 4. Components

Easing tokens: `--e-out: cubic-bezier(.16,1,.3,1)`, `--e-in: cubic-bezier(.7,0,.84,0)`,
`--e-io: cubic-bezier(.65,0,.35,1)`. Frames are 30 fps unless noted.

### 4.1 Bottom bar BB (persistent; CNN 2022 layout + Fox flip timing) - `cnn22_strip_senate_race_close.jpg`
- Box x 80..1840, y 876..1030 (154). Rows: header 876..926 (50, `--strip`), body rows 930..978 and 982..1030
  (48 each), 4 px dark gaps `--ink-2`.
- Block A, Senate balance, x 80..466: header "SENATE" (Oswald 600 46) + right caption "51 FOR MAJORITY" (13 px over
  25 px number). Tiles 930..1030: Dem x 80..270, Rep x 276..466, `--dem-700`/`--rep-700`; numeral 87 px white
  centred; label 18 px "DEMOCRATS"/"REPUBLICANS"; 20 px sub-strip (darker 15%) e.g. "34 NOT UP".
  Count only holdovers + AP projections relayed; uncalled seats stay out of both numbers.
- Block B, race flipper, x 476..1596: header = STATE (Oswald 600 46) + race (Oswald 400 32) + right meter
  "64% OF 2022 VOTE COUNTED": 10 segments 18x14 gap 3 (`--meter` / `--meter-off`), caption 13 px.
  Rows: party chip 48x48 (letter Roboto Cond 800 34 white) | SURNAME (55 px, `--ink` on `--plate`) |
  votes right-aligned at x 1452 (56 px) | % block x 1456..1596 party-700, white 51 px. Rows sorted by votes.
- Block C, bug x 1606..1840: white 876..990 with our generic logo, clock 26 px below it; footer 990..1030
  #414549 with channel tag 28 px white. Clock alternates "8:42 PM ET" / local time every 8 s, 300 ms crossfade
  (CNN alternates ET/PT; Fox cycles ET/CT/MT/PT).
- Flip: one race every 10.0 s (Fox measured 10.07 s). Per cell content fade-out 130 ms, left-to-right stagger
  200 ms (header -> left row -> right row), swap at 400 ms, fade-in 100 ms with the same stagger; colour blocks
  stay put. Total 770 ms (23 f). New-vote update in place: digits roll 600 ms, no flip.

### 4.2 Headline bar HB + tab (CNN reveal) - `cnn24_lowerthird_electoral_plus_state_strip.jpg`
- Tab x 80..480, y 724..768, `--tab`, label Figtree 800 40 px white ("UPDATE", "POLLS CLOSING", "AP PROJECTS").
- Bar x 80..1596, y 768..868 (100). Variants: `.hb--plate` white + `--ink` text (CNN); `.hb--alert` `--alert`
  + white text (NBC "NOW: VOTES BEING COUNTED IN GA, NC, PA"). Oswald 600 70 px, inset 40 px, single line.
- In: a `--tab`-coloured wiper block sweeps left->right 375 ms `--e-out`, text revealed behind it; tab rises
  210 ms starting at +250 ms. Total 460 ms (14 f). Out: content fade 125 ms then bar collapses 200 ms.
- Text swap without removing the bar: 125 ms fade out, 125 ms wipe in.

### 4.3 Results board `st_results` (CNN 2024 board, neutral base) - `cnn24_board_fullscreen_state_result.jpg`
- Panel x 80..1840, y 48..856, base `--navy-900` (CNN uses brand red; we stay party-neutral).
- Header 48..208: STATE Oswald 700 129 px white, inset 40; race tag "U.S. SENATE" white plate, red-ink text
  Oswald 600 42 px, at x 120, y 180..232 overlapping the header edge (CNN "PRESIDENT" tag); right block: seat note
  ("SPECIAL ELECTION", "SEAT HELD BY: R") 24 px caption over 46 px value.
- Rows from y 252, height 112, gap 18, max 4. Columns: chip 112x112 party-700 with letter 64 px | name plate
  `--plate` x 192..1260 (first 43 px / LAST 55 px, inset 24) | lead label "+31,167 AHEAD" right-aligned 35 px
  `--mute` above votes 70 px, both ending at x 1236 | % block x 1264..1840 party-700 (CNN uses 29% of row width),
  % 112 px right-aligned with 40 px inset. Leader row first; non-leaders same layout, no special treatment.
- Footer 790..850: left source line Figtree 500 22 px #C9CCD6 ("Source: Texas Secretary of State, 8:41 PM ET");
  right counted meter as in 4.1 but 22x22 segments, value 36 px.
- Build: see T2 in section 5 (rows rise 60 ms apart, numbers roll 600 ms).

### 4.4 Candidate cards `st_candidates` (ABC two-card, no photos) - `abc25_board_two_candidate_expected_vote.jpg`
- Header: white strip y 48..118 (title "U.S. SENATE - TEXAS", Figtree 800 46 px `--navy-900`); dark band
  #454545 y 120..230: race 64 px / state 50 px white, right-aligned status 41 px ("POLLS CLOSE 8 PM ET").
- Cards y 250..856, Dem x 80..938, Rep x 982..1840 (858 wide, 44 gap; ABC 838 / 53). Card = 8 px frame party-500,
  48 px left rail party-700 with faint stars (generic), body party-900.
- Name plate (replaces photo position) white, h 104 at top of body: first Figtree 300 48 px, LAST Figtree 800
  64 px in party-900, inset 32. Under it: party label chip ("DEMOCRAT" / "REPUBLICAN", 22 px caps) + "INCUMBENT".
- Facts: up to 4 items, Figtree 500 30 px white, line-height 1.25, <= 42 chars x 2 lines each, 18 px between
  items, each ending in an attribution line Figtree 400 italic 20 px at 70% white ("- campaign website").
- Results variant (when counting): bottom stat row h 120: % Figtree 800 135 px + votes 60 px; Dem card puts %
  right/votes left, Rep card mirrors (% faces the centre line, ABC). Vertical segmented meter 66 px wide inside
  the card edge facing centre: 14 px segments, 4 px gaps, lit = party-500, unlit = party-900.

### 4.5 Senators `st_senators`
- Two cards x 80..938 / 982..1840, y 250..560 using 4.4 styling at 60% height (plate + 2 facts). Seat-up card gets
  a `--yellow` tag "UP IN 2026" (black Oswald 600 32 px); the other a #5B5F6B tag "NEXT UP 2030".
- Strip below (y 600..700): previous result for the seat in 4.1 row style (year chip instead of party chip).

### 4.6 County map `st_counties` (CNN wall panel + NBC compare + ABC shades) - `cnn24_wall_county_fullscreen.jpg`, `nbc24_wall_county_vs_2020.jpg`, `abc25_wall_county_margin_shades.jpg`
- Map frame x 640..1840, y 48..856 on `--navy-950`; neighbouring states drawn in `--map-norace` with 1 px
  #0E1222 lines (ABC draws neighbours as outlines only).
- Fills: ramp from section 2. County lines 1 px rgba(0,0,0,.35); state outline 3 px #FFFFFF under 1.5 px #000.
- Focus county (from beat `focus`): 6 px #FFFFFF stroke + 2 px #000 outer (CNN double stroke), others dim to
  70% brightness over 300 ms; city/label: Figtree 800 30 px white caps, 2 px #000 shadow, 8 px white dot (ABC).
- Left panel x 80..620: title plate `--navy-900` @ 92%: "Harris County" Figtree 800 + " 2026" Figtree 300, 85 px
  (shrink to 60 px for long names), sub-plate "Senate" Figtree 400 48 px. Two rows h 130 gap 16: chip 100 |
  name block `--navy-800` (first Figtree 400 34 px / Last Figtree 800 56 px) | stat block party-500 (votes 37 px
  over % 80 px, % superscript). Footer plates: "84% counted" (bold %), context line Figtree 400 30 px:
  "16.3% of Texas votes · 2024: Trump +11.6" (CNN "Milwaukee, 16.3% (1 of 72), P2020 D+39.8").
- Optional compare column (NBC "2020 | PRES"): 200 px column right of the stats with the 2024 result in
  party-coloured text on white (winner cell filled).
- Callout (focus without panel change): 360x150 plate `--navy-900` with a 2 px leader line to the county
  centroid; enters with 200 ms scale 0.92->1 `--e-out`.

### 4.7 Votes left `st_votes_left` (NBC) - `nbc24_wall_expected_votes_remaining.jpg`
- Left x 80..1100: race rows in 4.6 style. Divider column x 1140..1180: vertical meter 40x465, lit (counted)
  `--yellow` from bottom, rest #9AA0A8.
- Right x 1210..1840 three stacked blocks with 1 px #C7CDC7 rules: "2022 TOTAL" (Oswald 500 37 px) + number
  (Roboto Cond 800 76 px) + "baseline" caption 30 px; "LEFT TO MATCH 2022" number + label; "COUNTED" number +
  12 px yellow dot + label. Never say "expected" (NBC/ABC/CNN expected-vote figures are proprietary models).
- Precincts line where published: "PRECINCTS 1,234 / 9,000 (13.7%)" 30 px.

### 4.8 History `st_history` (NBC/Telemundo side columns) - `tlm24_wall_county_with_history_columns.jpg`
- Table: columns "2024 | PRES" and "2020 | SEN" (the seat's previous race), 300 px each; header Oswald 600 40 px
  with a 2 px rule; per column two cells (dem/rep): name Oswald 600 36 px, % Roboto Cond 800 64 px, votes 30 px.
  Winner cell filled party-700 with white text; other cell white with party-coloured text (NBC "BIDEN 61.9%").
- Right half: 2024 county map at ramp colours, no focus stroke, legend "Margin" 4 swatches x 2.

### 4.9 Poll closing `st_poll_close`, `nat_schedule` (NBC countdown + Univision ladder) - `nbc24_lowerthird_poll_close_countdown.jpg`, `uni24_fullscreen_hora_de_cierre.jpg`
- Countdown row (takes BB block B+C area x 476..1840, y 876..1030, `--strip`): "8" Roboto Cond 800 110 px +
  stacked "PM"/"ET" 40 px | 2 px divider | "TEXAS" Oswald 700 80 px + " POLLS CLOSE" Oswald 400 80 px |
  yellow box x 1180..1590 `--yellow` "02:30" Roboto Cond 800 110 px black | "NEXT POLL CLOSING" box
  x 1600..1840 with 6 px `--yellow` border. Digits update every second with no animation (NBC); format mm:ss, ":13"
  under a minute (NBC drops the leading 0).
- After close: Telemundo-style elapsed timer "TIME SINCE POLLS CLOSED 09:21" with captions "MIN"/"SEC" 18 px.
- Full-screen ladder: column x 220..500, slots h 62 gap 8, Figtree 700 46 px; past slot #8D9196 text #C8CCD0;
  current `--gold` black text; future `--navy-900` with 2 px #C8CCD8 border. Map: closing now `--gold`, already
  closed `--map-closed`, not yet `--navy-950`, split-time-zone states hatched
  `repeating-linear-gradient(45deg,var(--gold) 0 14px,#111 14px 28px)`; postal labels 26 px white bold.

### 4.10 National map / balance / races (`nat_map`, `nat_balance`, `nat_races`)
- `nat_map`: map x 80..1420, y 60..856, AlbersUSA, AK/HI insets bottom-left. No 2026 Senate race
  `--map-norace`; polls open `--map-pending`; counting: leader tint dem-300/rep-300; AP-projected (relayed)
  party-700 + 18 px "AP" chip on the state. Lines 1.5 px `--map-line`. Right column x 1440..1840: legend + mini
  balance bar.
- `nat_balance` (CNN tiles + CBS bar) - `cbs24_lowerthird_senate_balance.jpg`, `cnn22_wall_national_house_tiles.jpg`:
  bar x 160..1760 (16 px per seat), h 64, y 520; Dem from left (holdovers dem-300, projected dem-700), Rep from
  right, undecided #BBBCBF middle; centre tick at x 960, 4 px white, 90 px tall, label "51 FOR MAJORITY". Tiles above:
  numbers Roboto Cond 800 160 px in party-700 boxes 300x220 (CNN "216 Democrats" tile), caption tiles 300x60
  ("12 races not decided").
- `nat_races`: list rows h 64 gap 6 (4.1 row style): state Oswald 600 46 px | D chip + surname + % | R chip +
  surname + % | counted meter | status chip ("POLLS OPEN" navy outline, "COUNTING" grey, "AP PROJECTS" dark slate
  + white). 10 rows per page, page dwell 8-10 s, rows cascade in 40 ms apart.

### 4.11 State intro `st_intro` (Fox board header) - `fox24_board_fullscreen_two_candidate.jpg`
- State name Figtree 900 caps, 110 px (Fox cap 80, very wide), `--plate` with 4 px `--navy-900` stroke and 6 px
  drop shadow, centred at y 120; race plate below: black #181818 plate 560x70 "U.S. SENATE" Oswald 600 60 px white.
- Two name plates (Fox "D | HARRIS"): 64x64 letter square + surname plate 420x64 Roboto Cond 700 60 px.
  Centre stack: "POLLS CLOSE 8 PM ET" 46 px over "SEAT NOW: R" 30 px.

### 4.12 Small persistent items
- LIVE: `--live` box 84x36, Figtree 800 24 px white ("LIVE", "EN VIVO", "ライブ", "直播"), x 80, y 40.
- AI disclosure: plate rgba(14,17,36,.72), h 36, Figtree 500 20 px white, right of LIVE; in-language text.
- Source line: always on data scenes, see 4.3 footer.
- Crawl (ja/zh; optional es): y 1030..1080 full width `--navy-950` (or TBS-like 155 px band if used as the main
  text channel); separators " ◆ " in `--gold`; content "TX SEN  CORNYN (R) 52.1%  TALARICO (D) 46.3%  45% COUNTED".
  Speed: 300 px/s for ja/zh at 64 px glyphs (TBS measured 299 px/s); Latin 150 px/s at 34 px caps (estimate, no
  US crawl was on air in the reference set). Newer-than-snapshot numbers go only here and in BB.

## 5. Transition catalogue (measured)

| id | name | source (frames) | timing | implement |
|---|---|---|---|---|
| T1 | hard cut studio<->board | CNN 2024 26.17 s | 0 ms | swap scenes with no tween; CNN's default between talent and full-screen |
| T2 | board build | ABC 2025 59.95-61.6 s (`abc25_board_build_mid.jpg`) | 1.65 s | old content dissolve 200 ms; header bar wipe L->R 400..930 ms `--e-out`; party slabs rise (scaleY 0->1, origin bottom) 534..734 ms, 40 ms apart; names/plates reveal 800..934 ms; numbers roll 1000..1600 ms |
| T3 | number roll-up | ABC 61.2 s | 600 ms | count from previous (or 0) with `--e-out`; % and votes together; tabular figures |
| T4 | HB reveal | CNN 2024 22.59-23.05 s | 460 ms | 4.2 |
| T5 | tier swap | CNN 2024 123.75-124.42 s | 700 ms | old out 125 ms; new left block slides from x-40 250 ms; header text +0, bars wipe 125 ms, names +125, % +210 ms |
| T6 | flipper | Fox, period 10.07 s | 770 ms | 4.1 |
| T7 | alert stripe wipe | NBC 149.6-150.6 s (`nbc24_alert_stripe_wipe_mid.jpg`) | 600 ms cover + 330 ms clear | 7 horizontal bars 60-120 px tall, `--yellow` and white alternating, enter from alternating sides 30 ms apart, 270 ms each `--e-io`, hold 1 f, exit same direction; HB builds under it 334..934 ms |
| T8 | diagonal shard wipe | CBS star wipe 27.70-28.37 s @60 fps (`cbs24_star_wipe_transition_mid.jpg`), Univision diagonal 4.67-4.83 s (`uni24_stinger_diagonal_wipe_mid.jpg`) | 650 ms / 330 ms | generic: 3 angled panels (25 deg) dem-700 / white / rep-700 sweep across, 60 ms apart, `--e-io`; no stars, no 3D glass |
| T9 | segment stinger | Univision 62.6-67.4 s | 4.8 s | fade to black 330 ms, black 1.1 s (we skip), title card fade-up 500 ms, hold 2.5 s with diagonal stripes sliding from corners, exit with T8 (330 ms) |
| T10 | map zoom nation->state | CNN 2022 126.0-126.9 s (`seq` zoom) | 750 ms | SVG viewBox tween `--e-io`; other states fade to `--map-norace` over first 300 ms; side panel stays fixed |
| T11 | dissolve | Univision camera changes, ABC board out | 200 ms | opacity crossfade |
| T12 | countdown tick | NBC | 1 s steps | text swap, no tween; at 00:00 HB tab "POLLS CLOSED" with T4 |
| T13 | callout / focus | (ours, from CNN/ABC styling) | 200 ms in, 150 ms out | 4.6 |

Entry order inside any scene (from ABC/CNN builds): background/plates -> header bar -> party blocks -> names ->
numbers (roll) -> meters -> source line. 40-80 ms between siblings, 120-200 ms between groups, whole build <= 1.6 s.
Start a scene's build 400 ms before its first sentence; never animate during the first 300 ms of a sentence
that carries a `focus` (let the stroke land first). State-to-state scene change: T7 (or T8) cover -> T1 swap under
cover -> T2 build. Beat change inside a scene: T5 (panel swap) or T10 (map). Within a beat only T3/T6/T13.

## 6. Which network to emulate, per scene

| scene / visual | emulate | notes |
|---|---|---|
| BB (all scenes) | CNN 2022 bottom bar + Fox flip timing | `cnn22_strip_senate_race_close.jpg`, `fox24_bottom_bar_senate_strip.jpg` |
| HB | CNN 2024 (plate) / NBC (alert) | |
| `nat_map` | CNN/NBC national map, Univision gold for closing states | `cbs24_ar_map_battleground.jpg` for state labels |
| `nat_balance` | CNN tiles + CBS centre-tick bar | Telemundo hemicycle (`tlm24_ar_senate_balance_seats.jpg`) is AR-only, skip |
| `nat_races` | CNN strip rows | |
| `nat_schedule` | Univision ladder | `uni24_fullscreen_hora_de_cierre.jpg` |
| `st_intro` | Fox board header | |
| `st_senators`, `st_candidates` | ABC two-card | photos replaced by name plates |
| `st_results` | CNN 2024 board | navy base instead of red |
| `st_counties` | CNN wall panel + ABC 4-step shades + NBC compare column | |
| `st_votes_left` | NBC expected-votes column | relabelled vs 2022 |
| `st_history` | NBC/Telemundo prior-year columns | |
| `st_poll_close` | NBC countdown row + Telemundo elapsed timer | |

Network fingerprints (to stay "close but generic"): CNN = condensed caps, white plates, red tab, tri-band
projection bar, navy wall with Bold+Light title, 10-segment green meter. Fox = heavy wide state names with stroke,
circles for %, lemon-yellow highlight, gradient crimson banner, flipping race strip, rotating time zones.
NBC = Kornacki light board with blue/red blocks, yellow progress bars, countdown boxes, stripe wipes.
ABC = geometric sans, mirrored two-card layout, vertical segment meters, white+grey header bands.
CBS = white rounded bar, photo tiles, thin balance bar with centre tick, 3D star glass wipes.

## 7. Language desks

Spanish (Univision, Telemundo): same red/blue and D/R letters (Demócrata/Republicano keep the initials).
Caps keep accents ("CÁMARA", "DEMÓCRATAS"). US number format. Observed labels: "HORA DE CIERRE", "8:00 PM ESTE",
"EN MINUTOS", "TIEMPO DESDE EL CIERRE", "MINUTOS / SEGUNDOS", "DEMÓCRATAS / REPUBLICANOS", "SENADO", "CÁMARA",
"Diferencia: 1,320", "CON 58%" (share counted), "ESTATAL" (statewide), "RESULTADOS". Use: "VOTOS CONTADOS",
"VENTAJA", "LE FALTAN PARA IGUALAR 2022", "CIERRE DE URNAS", "AP PROYECTA" (attributed). Univision's persistent
bar is a thin navy band (y 990..1080) with no ticker; Telemundo relies on wall + AR. Geometric sans (Figtree fits).

Japanese (TBS/JNN observed; NHK and Nikkei not captured, verify before copying anything specific to them):
- Horizontal text only in data graphics; no vertical text seen on TBS boards.
- Party colours: blue = Democrats, red = Republicans (TBS #0F2981 / #AC182B), same as US networks.
- Per-state header: state in katakana + "州" ("ジョージア州") left, right two-line caption "選挙人 16人 / 開票率 7.9%"
  (開票率 = share counted). Names "カマラ・ハリス" with middle dot; strips use the family name only.
- % with two decimals, decimals smaller ("39.94%"); TBS cards show % only (no vote counts).
- Layout: ivory/beige cards (#E3D1C1) over a blurred map on saturated purple; big white crawl (64 px) at
  300 px/s across a full-width purple band; 24/7 loop alternates map page and 4-5-state card grid, 9-18 s dwell.
- "当確"/"当選確実" stamps are race calls: we never draw them. Relay as text only: 「AP通信が当選確実と報道」.
- Terms: 上院, 改選 (up), 非改選 (not up), 過半数 51, 議席, 得票数, 得票率, 開票率 (only where precincts are
  published; otherwise 「集計済み 2022年比 64%」), 投票締め切り (poll close), 残り (left).

Traditional Chinese (FTV 民視, TVBS observed; CTi 中天 2024 US coverage not found on YouTube):
- Party colours blue = Democrats, red = Republicans (FTV #0644A9 / #A4013A, TVBS #4462DB / #C61721), not
  KMT/DPP colours. FTV adds donkey/elephant icons: do not copy party logos; use 民 / 共 chips or D / R.
- Taiwan transliterations (賀錦麗, 川普, 賓州, 密西根州, 喬治亞州); take 2026 candidate names from CNA (中央社).
  State + "州" (德州, 阿拉斯加州, 堪薩斯州, 緬因州, 俄亥俄州, 密西根州).
- Numbers bold italic with commas; % one decimal on a white box in party colour.
- Bottom stack goes to the frame edge: yellow title bar (#F1FF0D, black Noto Sans TC 900 84 px, y 855..975) +
  blue info bar (#0860F5) with date "11/04 (二) 21:15" and a flipper line; TVBS adds a persistent score bar
  (27 / 45.5% vs 53.4% / 99) above it. Guest name supers are vertical (FTV 李鎮宇): vertical text only for people
  supers, never data.
- Labels: 選舉人票數/19, 當選門檻 270, 未開 361, 決勝搖擺州, 參議院, 過半 51, 改選, 計票進度 64%, 得票數,
  得票率, 領先, 差距. "當選" stamps are calls: never draw; relay as 「美聯社預測 … 勝選」 with attribution.

## 8. Do not copy (and stand-ins)

| branded element | owner | our stand-in |
|---|---|---|
| network logos/bugs, show lockups (CNN, FOX NEWS channel, NBC peacock, abc, CBS eye, Univision, Telemundo T, TBS NEWS DIG, TVBS, 民視, 中天) | all | own generic channel mark |
| "Key Race Alert", "CNN Projection", "Magic Wall", "America's Choice", "Election Night in America", "#CNNELECTION" | CNN | "RACE UPDATE", "COUNTY MAP", "ELECTION NIGHT 2026" |
| "Democracy 2024/2026", "Fox News Decision Desk", "Fox News Alert", "Just Called", "America's Election HQ" | Fox | "UPDATE", "NEW VOTES IN" |
| "Decision 2024", "NBC Decision Desk", "Democracy Plaza", "Road to 270", "Big Board", "Kornacki Cam", "✓ ELECTION ALERT", "Too Early to Call" | NBC | "POLLS CLOSING", "COUNTING" |
| "Your Voice Your Vote", "Projected Winner" card | ABC | none (we do not call races) |
| "America Decides", "CBS News Decision Desk", "Battleground Tracker", "Live Estimate", 3D glass star wipe | CBS | T8 generic diagonal wipe |
| "Destino 2024", "Noche de Elecciones" lockup, "Línea de Fuego" | Univision | "ELECCIONES 2026 · EN VIVO" |
| "Decisión 2024", "Camino a los 270", "Batalla Final", AR Capitol hemicycle | Telemundo | "SENADO 2026" bar |
| "NEWS DIG", JNN; 当確 stamps | TBS | 「米中間選挙2026 開票速報」 |
| 「決戰白宮」, 「看民視」, 「白宮爭霸」, party donkey/elephant marks | TVBS / FTV / CTi | 「2026美國期中選舉 開票直播」 |
| "Est. Reporting", "Estimated Vote", "% Expected Vote In" (model-based estimates) | CNN / ABC / NBC / AP | "% of 2022 vote counted", "precincts reporting" |
| check marks / winner badges / "projected winner" | all | text-only "AP PROJECTS ... (Associated Press)" in HB |
| election music packages, stingers, sound logos | all | original or licensed library audio |
| set pieces: CNN tri-band ★★★ projection bar, Fox White House virtual set, NBC 3D White House, CBS star | CNN / Fox / NBC / CBS | flat navy panels |

## 9. Frame index (`research/election/frames/`)

- `abc25_board_two_candidate_expected_vote.jpg` ABC mirrored two-card board, "33% EXPECTED VOTE IN" header right.
- `abc25_board_build_mid.jpg` ABC build mid-way: header bar wiping, party slabs rising (T2).
- `abc25_wall_county_margin_shades.jpg` ABC county map, 4-step margin shades, city dots/labels (f).
- `abc25_lowerthird_name_super.jpg` ABC thin red lower bar with LIVE box and name super.
- `cbs24_ar_map_battleground.jpg` CBS AR national map, purple toss-ups, postal labels.
- `cbs24_ar_state_board_vote_in.jpg` CBS state header "GEORGIA ▸ PRESIDENT / 33% VOTE IN / 16 EV", two-candidate %.
- `cbs24_lowerthird_senate_balance.jpg` CBS white bar: race tiles + "30 NEW SENATE 41" bar with centre tick.
- `cbs24_star_wipe_transition_mid.jpg` CBS 3D star glass wipe mid-frame (branded; reference for T8 timing only).
- `cbs24_touchscreen_county_map.jpg` CBS touchscreen county map + candidate blocks, double-box layout.
- `cnn22_bottom_bar_balance_and_race_strip.jpg` CNN 2022 bar over studio wall, "U.S. HOUSE 38/34" wall tiles.
- `cnn22_strip_senate_race_close.jpg` CNN 2022 bar: SENATE 48/47 tiles, "NEEDED TO CONTROL 51", GA race strip.
- `cnn22_wall_district_fullscreen.jpg` CNN wall: Bold+Light title, "16,981 Ahead", Incumbent tag, outline stroke.
- `cnn22_wall_national_house_tiles.jpg` CNN wall national tiles "216 Democrats / 219 Republicans", "435 Reporting".
- `cnn24_board_fullscreen_state_result.jpg` CNN full board: state header, rows, % blocks, 10-segment meter.
- `cnn24_lowerthird_electoral_plus_state_strip.jpg` CNN 3-tier lower third: tab, headline, EV box + state strip, bug.
- `cnn24_lowerthird_standby_projection.jpg` CNN "stand by" projection bar (branded; do not copy).
- `cnn24_wall_county_2020_history_toggle.jpg` CNN wall same county toggled to 2020 (history pattern).
- `cnn24_wall_county_fullscreen.jpg` CNN wall county panel + "16.3% (1 of 72), P2020 D+39.8" context line.
- `cnn26_board_candidate_headline_card.jpg` CNN 2026 Texas Senate analysis card (headshot + big number).
- `fox24_board_fullscreen_two_candidate.jpg` Fox virtual-set board: heavy state name, % circles, IN/DIFFERENCE.
- `fox24_bottom_bar_race_strip_and_banner.jpg` Fox crimson banner + race strip + "NEEDED TO WIN" box.
- `fox24_bottom_bar_senate_strip.jpg` Fox strip on a Senate race (WYOMING SENATE), board above.
- `fox24_sidebar_board_over_studio.jpg` Fox side-panel board over a two-shot.
- `ftv24_panel_map_swing_yellow.jpg` FTV map with yellow swing states, 72/105 header.
- `ftv24_panel_state_result.jpg` FTV state panel (賓州), vertical guest super, yellow title bar, blue info bar.
- `nbc24_alert_stripe_wipe_mid.jpg` NBC yellow/white stripe wipe mid-frame (T7).
- `nbc24_board_poll_closings_alert.jpg` NBC "POLL CLOSINGS :03" board + alert lower third.
- `nbc24_board_too_early_to_call_bar.jpg` NBC 3D two-candidate bar (call language; layout reference only).
- `nbc24_lowerthird_poll_close_countdown.jpg` NBC countdown row: "8PM ET PENNSYLVANIA POLLS CLOSE 02:30" + next box.
- `nbc24_lowerthird_results_strip_pct_in.jpg` NBC results strip: state, EV, "77% IN", leader first.
- `nbc24_wall_county_vs_2020.jpg` NBC board: county, "76% IN" bar, 2020 PRES compare column, yellow focus outline.
- `nbc24_wall_expected_votes_remaining.jpg` NBC votes-left column: expected / remaining / reported + yellow meter.
- `nbc24_wall_remaining_vote_bubbles.jpg` NBC remaining-vote bubbles on county map.
- `tbs24_auto_board_state_grid.jpg` TBS 4-state card grid: 選挙人/開票率 headers, katakana names, bars.
- `tbs24_auto_map_electoral_bar_crawl.jpg` TBS map page with electoral bar and big white crawl on purple.
- `tlm24_ar_senate_balance_seats.jpg` Telemundo AR "DEMÓCRATAS 47 - 49 REPUBLICANOS SENADO".
- `tlm24_wall_270_balance_columns.jpg` Telemundo "CAMINO A LOS 270" columns with 270 line.
- `tlm24_wall_county_with_history_columns.jpg` Telemundo county board with 2020/2016/2012 columns, "CON 58%".
- `tvbs24_bottom_bar_electoral.jpg` TVBS yellow title bar + persistent electoral score bar.
- `uni24_fullscreen_hora_de_cierre.jpg` Univision poll-closing ladder + gold/grey/navy/hatched map.
- `uni24_stinger_noche_de_elecciones.jpg` Univision segment title card (branded lockup; timing only).
- `uni24_stinger_diagonal_wipe_mid.jpg` Univision diagonal red wipe mid-frame (T8/T9).

Clips (`research/election/clips/`, offsets in `offsets.txt`): cnn_2024_projection_wall, cnn_2022_king_wall,
cnn_2026_tx_senate, fox_2024_alerts, nbc_2024_pollclose_8pm, cbs_2024_8pm_boards (60 fps), abc_2025_va_boards,
telemundo_2024_boards, univision_2024_cierre, tbs_2024_auto_board, tvbs_2024_bar, ftv_2024_panel.

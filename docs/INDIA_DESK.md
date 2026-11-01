# India desk (Cyclone Arnab, North Indian Ocean): shared spec

Streams: `india-te` (Telugu, Andhra Pradesh focus) and `india-ta` (Tamil, Tamil Nadu focus). Same data, different
language and emphasis. Landfall: Andhra Pradesh coast (IMD: between Bapatla and Visakhapatnam, near Kakinada / Yanam),
morning of Wed 28 Oct 2026 IST. Go-live target: Tue 27 Oct, early morning IST.

Rules (same as Taiwan / Japan): narration and on-screen claims come from official text (IMD first; JTWC only as a
labelled second opinion for track geometry), every item carries its issue time, nothing invented. India's Disaster
Management Act s.54 penalises false warnings. No AI or stock disaster imagery: real satellite, real maps, real cameras.

## Data: desk.json for the India streams (DESK_DIR=output/desk/india, EC2 streams india-te and india-ta)

Built by `python -m desk.updater` with `DESK_REGION=nio` (default stays the Western Pacific builder). Keys the page and
the narration rely on:

```
storm      {"title": "CYCLONIC STORM", "name": "ARNAB", "names": "...", "jtwc_id": "io0226"}
center     {"lat", "lon", "timeUTC", "source": "IMD" | "JTWC"}
forecast   {"source", "issuedUTC", "points": [{"timeUTC", "lat", "lon", "wind_kmh", "label"}]}   # IMD's track if available, else JTWC's
past       {"source", "points": [[timeUTC, lat, lon, kt], ...]}
agencies   [{"agency": "IMD" | "JTWC", "sub": "3-min" | "1-min", "time", "timeUTC", "winds", "gusts", "pressure", "moving", ...}]
in: {
  "imd": {
    "issuedUTC", "issued_ist_text",            # e.g. "1430 hrs IST of 26 October"
    "bulletin": "...",                          # bulletin name / number as IMD gives it
    "class": "Cyclonic Storm",                  # IMD classification (Depression .. Super Cyclonic Storm)
    "position_text": "...",                     # IMD's own sentence: "about 650 km east-southeast of Visakhapatnam ..."
    "movement_text": "...", "lat", "lon",
    "wind_text": "...", "wind_kmh": 90, "gust_kmh": 100, "pressure_hpa": 990,
    "landfall_text": "...",                     # IMD's own sentence
    "landfall": {"between": ["Bapatla", "Visakhapatnam"], "near": "Kakinada", "time_text": "morning of 28 October",
                 "timeUTC": "...", "class": "...", "wind_kmh": 110, "gust_kmh": 120},
    "surge_text": "...", "rain": ["..."], "wind_warnings": ["..."], "sea_text": "...", "fishermen_text": "...",
    "forecast": [{"timeUTC", "lat", "lon", "wind_kmh", "gust_kmh", "class"}],
    "source_url": "..."
  },
  "districts": {"Andhra Pradesh": {"Kakinada": "red", ...}, "Tamil Nadu": {...}, "Odisha": {...}},   # IMD colour levels, if obtainable
  "districts_issued": "...",
  "cpa": [{"place", "km", "timeUTC"}]          # from the official track: Visakhapatnam, Kakinada, Machilipatnam, Chennai ...
}
```

Missing pieces must be absent (never guessed); the page and narration hide what is missing.

## Page: html/india-desk.html (?lang=te | ?lang=ta), served for streams whose id starts with `india`

High-energy Indian news look (see research/market/thumbnails_india.md): red / saffron / yellow, bold Telugu or Tamil
text with English mixed in ("CYCLONE ARNAB LIVE", "IMD"), but every number from IMD. Scenes rotate:
1. Track map: Bay of Bengal (about 8-24 N, 76-94 E), satellite, IMD track + cone / JTWC as labelled second line, Andhra
   Pradesh / Tamil Nadu / Odisha state outlines, cities (Visakhapatnam, Kakinada, Machilipatnam, Bapatla, Nellore,
   Chennai, Puducherry, Bhubaneswar, Puri), big LANDFALL COUNTDOWN (to IMD's landfall time) in the local language.
2. District alert board: AP (te) or TN + AP (ta) district map coloured by IMD alert level, with the list.
3. IMD bulletin card: class, position, wind/gust km/h, pressure, landfall, surge, fishermen warning: big numbers.
4. Live cameras on the coast (ids in html/india-cams.json).
Header with IST clock, LIVE pill, storm name in the local script (te: అర్నాబ్ తుఫాన్ ; ta: அர்னாப் புயல்), ticker and lower
third in the local language from desk "in" data. Live narration playback identical to champi-desk.html (live/current.json,
captions, audio, playback heartbeat), so the pipeline and encoder work unchanged.

## Narration (src/desk/bulletin.py templates in_te_*, in_ta_*), voice: MMS-TTS (te, ta) for now

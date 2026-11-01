# Cyclone live thumbnails for Telugu and Tamil audiences (research for Cyclone Arnab, Oct 2026)

Sample: 36 Telugu and 30 Tamil live-stream thumbnails. They are the top streams for Arnab (so far), Montha 2025, Michaung 2023 and Fengal 2024,
plus views-per-subscriber outliers and the weakest streams from 1M+ channels. Images and `index.csv` are in `output/youtube/competitors_in/{te,ta}/`,
with contact sheets `_sheet_{te,ta}_{A,B,C}.jpg` and phone-size strips `_phone_{te,ta}.jpg`. Title statistics cover all 199 Telugu and 180 Tamil
streams in `research/market/cache4` and `cache2`.

## Is it more dramatic than Taiwan and Japan?
Visually yes, but with less information on screen.
- **Imagery.** About 12 of the top 25 Telugu thumbnails and 7 of the top 20 Tamil ones use stock or AI disaster art: tornadoes, tsunami-sized
  waves, a whirlpool, and the Charminar under an AI storm. Very few show real imagery of the storm itself.
  - Telugu: about 3 of 25 show a real satellite image or IMD map of the storm (screenshots of IMD maps or Windy).
  - Tamil: real satellite or radar in 10 of 20, maps in 7 of 20.
- **Colour and text.** Red is the main colour (red text, solid red panels, white boxes behind text). Two large lines of local-script text
  usually fill about half the frame, often in brush or 3D lettering.
- **Fear commands and stakes.** 「ఎవరు బయటకు రాకండి」 / 「బయటకు రావొద్దు」 ("nobody go outside"), 「వీட்டைவிட்டு வெளியே வராதீர்!!」, 「ఇక బీభత్సమే!!」 ("now it's havoc"), death tolls
  (「5 గురు మృతి」, "5 dead").
- **Fewer hard numbers.** Wind speed appears in only 6 of 25 Telugu and 1 of 20 Tamil thumbnails.
  - Freshness stamps (date or time) appear mostly on Tamil scheduled bulletins (PT Headlines 「மாலை 5 மணி」 + date) and the independent
    「muthuselvam weather man」 (date + 「அடுத்த 3 மணி நேரம் பேய்மழை」, "torrential rain for the next 3 hours").
  - Only one countdown appeared: 「FENJAL COUNTDOWN STARTS」.
  - Our Taiwan and Japan thumbnails carried more data (wind level, countdown, a storm ring drawn to scale) and were calmer in colour.

## Findings
1. **The thumbnail is not the main differentiator.** The weakest big-channel streams (3–5k views) look almost the same as the 1M-view ones.
   Timing and channel reach matter more. Streams with a landfall phrase (「తీరం దాటిన / తీరాన్ని తాకింది」) have a median of 139k views against
   49k without (19 of 199). The biggest spikes come around landfall.
2. **Faces are common but not dominant.** Telugu: 8 of 25 (3 Chief Minister Naidu, 3 weather officers or presenters pointing at maps, 2 field reporters).
   Tamil: 4 of 20 (anchor, weather explainer, IMD official, reporter in a flooded street).
3. **Local geography is the strongest honest hook.**
   - **Telugu:** a red Andhra Pradesh or Telangana silhouette with an arrow appears in 15 of 25. Named districts or cities
     (Kakinada, Bapatla, Nellore, Hyderabad, 「ఈ జిల్లాలకు」, "these districts") go with a median of 79k against 53k.
   - **Tamil:** naming Chennai or Tamil Nadu goes with 176k against 137k.
   - **Small channels:** the views-per-subscriber outliers are local reporters on the coast (「కాకినాడ తీరం వద్ద ప్రస్తుత పరిస్థితి」, "current situation at the Kakinada coast";
     「బాపట్ల తీరంలో」, "on the Bapatla coast").
4. **An English tag in the title helps.** People search the English name. Titles containing "Cyclone X" have a median of 94k against 15k in Telugu (171 of 199)
   and 187k against 149k in Tamil. A short English strip on the thumbnail is common ("CYCLONE MONTHA UPDATES", "RAIN BREAKING", "BREAKING").
5. **Words that go with higher views:** 「రెడ్ అలర్ట్ / ரெட் அலர்ட்」 ("red alert") in Tamil (439k against 159k, 12 titles); km/h numbers (125k against 56k, 5 Telugu titles);
   school and holiday closures (「విద్యా సంస్థలకు సెలవు」, "holiday for educational institutions": TV9 Telugu's top streams, 379k median).
   **Overused or weaker:** 「దూసుకొస్తున్న」 ("rushing in": 42 titles, 32k against 72k), LIVE as the first word (30k against 92k), and 「எச்சரிக்கை」 ("warning") on its own.
6. **Telugu and Tamil look different.**
   - **Telugu:** AI art, faces of politicians, commands, and AP silhouettes.
   - **Tamil:** BREAKING or RAIN BREAKING labels, half-frame red panels, more real satellite imagery, question hooks
     (「தாக்குப்பிடிக்குமா தமிழ்நாடு?」, "will Tamil Nadu hold out?"; 「கரை கடப்பது எங்கே, எப்போது?」, "where and when will it cross?"), and rain for Chennai.
   - **Tamil table stakes:** 🔴 and LIVE (161 and 159 of 180).
7. **Spellings:**
   - **Telugu:** 「అర్నబ్」 is the most frequent (15 titles); 「అర్నాబ్」 has the most views (3.1M, the top SumanTV streams).
   - **Tamil:** 「அர்னாப்」 in every title.

## Risky patterns we will not copy
- **Fake imagery:** AI or stock disasters (tornadoes, tsunami walls, cities under AI storms) shown as if they were this storm, in about 40% of Telugu thumbnails.
- **Exaggeration:** BIGTV Karimnagar's 1.06M-view Montha thumbnail says 「200 కిలోమీటర్ల వేగంతో తీరాన్ని తాకేసింది」 ("hit the coast at 200 km/h"), but its own title said 110 km/h.
- **Implied endorsement:** politicians' faces, which would suggest endorsement of an automated stream.
- **Fear commands with no source.** India's Disaster Management Act 2005, §54, penalises false warnings. We use only IMD numbers,
  real satellite imagery, named districts, and IMD's landfall window.

## Spec: our Arnab thumbnails (1920×1080, using the existing thumb-tw.html engine)
- **Imagery:** the real Himawari or INSAT enhanced-IR sector with the storm and the coast in frame. The AP silhouette (Telugu) or the TN and AP outline (Tamil)
  in thick red or yellow. A red circle around the storm and an arrow toward the IMD landfall area (Kakinada–Yanam). No faces: we have no anchor,
  and borrowed faces would mislead. The honest substitute is a pointer and arrow on the real map, plus a "Source: IMD" chip (text only, not the IMD logo).
- **Top strip:** a red LIVE badge, the IST date and time stamp, and an English tag "CYCLONE ARNAB LIVE". Top right: a fixed brand tag.
- **Text:** two big lines in Telugu or Tamil (yellow, then white, with one word in red) on a dark band. Tamil variant: a half-frame red panel on the left instead.
  A small third line names districts. A wind chip shows IMD km/h.
- **Updates:** the countdown and stamp refresh hourly; the words change when IMD's bulletin changes, as on the Taiwan stream.

### Telugu text sets
1. 「అర్నాబ్ తుఫాన్ తీరం దాటడానికి **{N} గంటలు**」 / 「గంటకు **{wind}–{gust} కి.మీ** వేగంతో గాలులు」 / 「{districts}కు రెడ్ అలర్ట్ • IMD」
   (Arnab hits the coast in {N} hours / winds of {wind}–{gust} km/h / red alert for {districts} • IMD)
2. 「**{day} {time}కి** తీరం దాటనున్న అర్నాబ్」 / 「కాకినాడ • యానాం • విశాఖ అప్రమత్తం」 / 「సముద్రం {surge} మీటర్లు ముందుకు • IMD హెచ్చరిక」
   (Arnab to hit the coast at {day} {time} / Kakinada, Yanam, Visakhapatnam on alert / sea surge of {surge} m • IMD warning)
3. After landfall: 「తీరం దాటిన అర్నాబ్ తుఫాన్」 / 「{districts}లో అతిభారీ వర్షాలు」 / 「IMD తాజా బులెటిన్ • LIVE」
   (Arnab has hit the coast / very heavy rain in {districts} / latest IMD bulletin • LIVE)

### Tamil text sets (Tamil Nadu's story is rain; the landfall is in Andhra Pradesh)
1. 「அர்னாப் புயல் கரையை கடக்க **இன்னும் {N} மணி நேரம்**」 / 「மணிக்கு **{gust} கி.மீ** வேகத்தில் காற்று」 / 「{districts} கனமழை எச்சரிக்கை • IMD」
   (Arnab crosses the coast in {N} hours / winds of {gust} km/h / heavy-rain warning for {districts} • IMD)
2. Tamil red-panel style: 「RAIN ALERT」 / 「{districts}க்கு **ரெட் அலர்ட்**」 / 「அர்னாப் புயல் • IMD அறிவிப்பு」
   (red alert for {districts} / Cyclone Arnab • IMD announcement)
3. 「அர்னாப் புயல் கரை கடப்பது **{day} {time}**」 / 「தமிழகத்தில் என்ன நிலவரம்?」 / 「சென்னை மழை • நேரலை」
   (Arnab crosses the coast at {day} {time} / what's the situation in Tamil Nadu? / Chennai rain • live)

All placeholders are filled only from IMD bulletins (sustained wind and gust in km/h, landfall window, surge, districts under red or orange
warnings). Red alerts appear only when IMD or the state disaster authority has issued them. Telugu titles include "Cyclone Arnab" in English, and use LIVE as a tag, not as the first word.

# US midterms 2026: is there a live-stream market outside English?

Measured 2026-11-01 (election Tuesday 2026-11-03). YouTube numbers: `measure.py us_midterms.json --cache cache5`
(completed live streams found by search, titles filtered to the event; lifetime views incl. replays; search returns at
most 50 streams, and 24/7 news channels whose titles don't name the event are missed). Web research by three agents.

## The 2022 midterms by language (the direct analog)

| Language | Live-stream views | Streams | To big channels (>=1M subs) | Best small channel (<100k subs) |
|---|---|---|---|---|
| English, national | 10.0M | 36 | 91% | none |
| Spanish | ~0.6M | 12-17 | 93-98% (Telemundo 248k, Univision 138k) | 3.8k |
| Chinese (diaspora + Taiwan) | ~0.45M | ~25 | 35-83% (NTD, TVBS, 王剑) | 詢經問道 11k |
| Japanese | ~0.19M | ~6 | ~15% | ポリタスTV 61k, やすの米国株 5.9k |
| Vietnamese (diaspora) | 0.13M | 4 | 1% | Nguoi Viet Channel 38.6k |
| Russian / Persian / Ukrainian | 89k / 76k / 44k | 1-5 | exile and US-funded media | none |
| Korean | ~33k | 2-3 | 0% | MKim TV (193k subs) 30.6k |
| French (native) | ~15k | 4 | 0% | 4.4k |
| Hindi, Arabic, Tagalog, Portuguese, German | no dedicated streams found | | | |

Midterms draw 1-5% of a presidential year's live views in each foreign language: 2024 had Spanish 17.4M, Vietnamese
11.3M, Chinese 9.2M, Portuguese 9.0M, Japanese 7.4M, Korean 0.3-4M, and the large outlets took 70-99% of them.

## Per-state streams

- **English:** local TV owns this market.
  - 2022: Georgia 0.69M (11Alive 282k), Arizona 1.0M (FOX 10 Phoenix 326k, India's Times Now 409k), Texas 0.23M (WFAA 135k), Michigan 65k, Wisconsin 35k. NC, NY, CA, OH, PA and NV each had at most 41k.
  - Georgia runoff 2022: 1.07M; 13WMAZ alone got 550k.
  - Small channels' best results: Jaye De Black 19.9k (Georgia 2022), CRPA TV 15.4k (Prop 50, 2025), NJ Spotlight News 14.5k (NJ governor, 2025). Most got a few thousand or less.
- **Spanish:** almost nothing on either side. Univision San Antonio drew 3.7k and Univision Los Angeles 3.3k. Orlando and Tampa streams got under 100 views. Nothing was found for Arizona, Nevada or Spanish-language Prop 50.

## Constraints

- **Results data:**
  - The AP and Decision Desk HQ APIs are sold through sales teams only and can't be obtained in two days.
  - Official state and county results sites are free (Clarity ENR serves about 1,000 jurisdictions in ~30 states). Their election IDs aren't known until they appear, and there is no common schema.
  - Never scrape AP, DDHQ or network results pages.
  - Never call a race yourself. Say "leads"; relay a call only as "AP projects", with attribution.
- **YouTube:**
  - In 2022, more than 85% of election search results came from "quality news" sources. The home-page live shelf (English and Spanish) and the Top News shelves favour outlets that appear in Google News.
  - Election content must carry an AI-voice disclosure.
  - Expect a risk to monetization under the "inauthentic content" rules, and limited ads.
- **Status of US-funded language services in late 2026:**
  - Voice of America: the Vietnamese, Cantonese, Haitian Creole and Somali services have been dark since March 2025.
  - RFA Cantonese: dark since June 2025.
  - Still running: VOA Mandarin, Persian, Korean, Russian and Ukrainian.
  - A real gap exists only in Vietnamese and Cantonese. Vietnam's state media is already streaming the US race in Vietnamese (Báo Hà Tĩnh: 97-131k views per stream).
- **Timing:** polls close from 7 pm ET (00:00 UTC Nov 4) to 1 am ET. That is Wednesday 09:00-15:00 in Japan, and Wednesday morning in Vietnam.

## Verdict

- **Japanese** is the only cell that looks like our earlier wins: about six streams, small channels taking a large share, and results arriving in Japan's daytime.
  - Expected result: 5-20k views if 2026 interest is similar to 2022. That is comparable to our typhoon streams, not a breakout.
  - Its catch: viewers want national control of the Senate and House, which needs licensed national data. A stream limited to official counts would have to stick to a handful of key Senate races.
- **Vietnamese diaspora** comes second: VOA's gap is real, but it carries the same risk as our India runs (the channel has no audience there, and domestic state media compete).
- **Not worth it:**
  - Spanish, national or per-state: networks own national coverage, and Spanish per-state streams barely exist.
  - English per-state: local TV owns it, and small channels peak around 15-20k.
  - Korean, Russian, Persian, Hindi, Arabic and Tagalog.
- **The real prize is the 2028 presidential election,** when foreign-language demand is 20-100x larger.

## Timing: when demand builds and peaks (added 2026-11-01)

Sources:
- Hourly Wikipedia pageviews for the 2022 election articles, 72 hours from Wikimedia's hourly dumps. The file hour marks the end of its hour, checked against the 17:30 UTC Elizabeth II announcement. Reading Wikipedia is a proxy for interest, not for live-stream viewers.
- Start and end times of the 2022 streams, from `videos.list`.
- Published figures: CNN digital, Fox/Nielsen and Streams Charts.
- ET on Nov 3, 2026 is UTC-5, and JST is ET+14.

**English, national:**
- Interest was at 38% of peak at 4 pm ET, 62% at 7 pm and 90% at 9 pm. It peaked from 10 pm to 1 am, then fell to 71% at 3 am.
- A second wave came on Wednesday from 7 am to 1 pm ET, at 85-91% of peak.
- TV: Fox's 2022 peak was the 9 pm hour, and the 11 pm hour was at 74%. CNN digital peaked at 10:03 pm ET with a flat plateau from 8 to 11 pm, and again at 12:35 pm Wednesday (94% of the night's peak).
- The big streams went live between 5 and 7:15 pm ET and ran until 1-4 am. They went live again on Wednesday morning: LiveNOW drew 743k from 06:30 to 16:55, and CBS 458k.

**English, per-state Senate and governor races (GA, PA, AZ, NV):**
- Interest peaks later, from 11 pm to 1 am ET (83% at 10 pm).
- Wednesday morning runs at about 70% of peak, and slow-count states hold interest for days.

**Spanish:**
- Spanish Wikipedia readers, mostly in Latin America and Spain, peak earliest, at 8-9 pm ET. Interest was down to 65% by midnight and about 50% through Wednesday.
- Telemundo and Univision were live from about 8:45 pm to 3 am.

**Japanese:**
- Japanese demand happens in Japan's Wednesday daytime. Japanese Wikipedia peaked at 12:00 JST (10 pm ET), though its counts are small and noisy.
- 2020: TBS's 08:00-19:33 JST stream drew 795k, the overnight part 348k and the next day's 241k.
- 2024: TBS ran from 09:08 to 20:50 JST and drew 1.34M. Its evening follow-on drew 252k.
- 2022: ポリタスTV ran from 07:23 to 19:04 JST.
- 2026: Niconico has already scheduled a stream for 11:00 JST.

**Chinese (Taiwan, Hong Kong and diaspora):**
- Chinese Wikipedia peaked from 10 pm to 3 am ET (11:00-16:00 Taiwan time).
- Diaspora streams ran from 8 to 11 pm ET. Taiwanese TV peaked in the daytime (TVBS 2024: 08:59-16:00 drew 1.44M against 268k in the evening).

**Vietnamese:**
- The diaspora streams (Nguoi Viet, VietFace) ran from 8 pm to 3 am ET.
- Vietnam's state media in 2024 streamed from 06:00 to 15:00 ICT (6 pm to 3 am ET).
- Vietnamese and Korean Wikipedia counts are too small to read anything from.

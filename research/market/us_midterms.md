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

# Election-night baseline: data, geometry, sources (built 2026-11-02)

## What was built

| file | content |
|---|---|
| `data/election/baseline/{TX,AK,KS,ME,OH,MI}.json` | ELECTION.md "Baseline" schema: statewide + per-unit `pres2024`, `sen_prev`, `turnout2022`, `sources` |
| `html/election/geo/us-states.json` | 50 states + DC, `{id: postal, fips, name}`, 140 KB |
| `html/election/geo/<ST>.json` | unit polygons, `{id, name}` equal to the baseline units: TX 295 KB, AK 273 KB, ME 117 KB, MI 98 KB, OH 61 KB, KS 45 KB |
| `data/election/senate_holdovers.json` | the 65 seats not up in 2026, by state and party, plus composition and the 35 seats up |
| `tests/election/test_baseline.py` | offline validation (62 tests, pass): `python -m pytest tests/election/test_baseline.py` in the project env |

Units: 5-digit county FIPS; Alaska `AK-HD01`..`AK-HD40` (the 2022 house-district plan), named "House District N";
`unit_type` is `"county"`, or `"house_district"` for Alaska. Unit names are the Census `NAME` ("DeWitt", "St. Clair").

### Additions to the schema (all optional; the documented keys are unchanged)
- `not_in_units`: votes the state reports outside every unit, with a `note` explaining them. The identity
  `statewide = sum(units) + not_in_units` holds exactly for every measure, and the test enforces it. A file without this
  key has unit sums that equal statewide exactly (TX, MI).
- `notes`: free-text discrepancies and choices. `sen_prev.note` exists for AK (Gross) and ME (first round).
  `sources[].note` gives detail where needed.

## Statewide sanity numbers (certified)

| ST | Harris | Trump | other | total 2024 | previous election for the seat (dem / rep / other / total, winner) | turnout2022 |
|---|---|---|---|---|---|---|
| TX | 4,835,250 | 6,393,597 | 159,827 | 11,388,674 | 2020 Hegar 4,888,764 / Cornyn 5,962,983 / 292,293 / 11,144,040 (REP) | 8,102,908 (governor votes) |
| AK | 140,026 | 184,458 | 13,693 | 338,177 | 2020 Gross 146,068 / Sullivan 191,112 / 17,407 / 354,587 (REP) | 267,047 ballots |
| KS | 544,853 | 758,802 | 23,936 | 1,327,591 | 2020 Bollier 571,530 / Marshall 727,962 / 68,263 / 1,367,755 (REP) | 1,020,208 ballots |
| ME | 435,652 | 377,977 | 17,746 | 831,375 | 2020 Gideon 347,223 / Collins 417,645 / 54,315 / 819,183 (REP, first round) | 680,909 ballots |
| OH | 2,533,699 | 3,180,116 | 53,973 | 5,767,788 | 2022 Ryan 1,939,489 / Vance 2,192,114 / 1,739 / 4,133,342 (REP) | 4,201,368 ballots |
| MI | 2,736,533 | 2,816,636 | 111,017 | 5,664,186 | 2020 Peters 2,734,568 / James 2,642,233 / 102,919 / 5,479,720 (DEM) | 4,500,400 ballots |

All 2024 and previous-Senate statewide numbers match the FEC compilations of certified results exactly:
`2024presgeresults.xlsx`, `federalelections2020.pdf` and `federalelections2022.xlsx` at fec.gov. The test hard-codes them.
`total` counts every vote cast for the office, write-ins included, but not over- or under-votes. `other = total - dem - rep`.

## Sources and choices per state

**TX** (all from Texas Secretary of State certified canvass reports, `https://results.texas-election.com/static/data/Reports/<id>/`)
- **Reports used:** `CountybyCountyCanvassReport.xlsx` and `OfficialCanvassReport.xlsx`. The ids are 49664 for the 2024 general, 44144 for 2020 and 47009 for 2022. The site rejects curl's default User-Agent; a browser User-Agent works.
- **turnout2022 is governor total votes, not ballots cast.** The SOS publishes no per-county ballots-cast figure for 2022: its VoterTurnoutReport returns 404. The SOS's own "turnout" figure is this governor total.
- **Rejected alternative:** the Texas Legislative Council's VTD-level ballots cast sums to 8,143,047 (+0.5%). It isn't reconciled to the canvass: 5 counties show fewer ballots than governor votes. I kept it as a cross-check only.
- **Unit sums:** county sums equal statewide exactly. Overseas ballots are canvassed in the voter's county.
- **2026 live results** are on the Civix ENR: `https://goelect.txelections.civixapps.com/ivis-enr-ui/races`.

**AK** (Alaska Division of Elections)
- **pres2024:** `results/24GENR/ENRbyPrecinct.csv`, with district Absentee, Early and Question rows counted in their district.
- **sen_prev:** the 2020 Statement of Votes Cast per old district, `results/20GENR/data/sovc/HD1p.pdf`..`HD40p.pdf`, cross-checked against `resultsbyprecinct.txt`.
- **turnout2022:** ballots cast ("Voters Cast") per district, from `results/22GENR/HD1.pdf`..`HD40.pdf`. The statewide figure of 267,047 is from the Election Summary Report.
- **Overseas bucket:** HD99 "Fed Overseas Absentee" ballots are federal-only overseas ballots that sit outside every district. They are stored in `not_in_units`: pres 401, senate 409, turnout 104.
- **Gross:** Al Gross is recorded as `dem`, with a note: he was a registered nonpartisan who ran as the Alaska Democratic Party's nominee.
- **Map check:** the 2022 and 2024 precinct lists share 400 identical code and name pairs with the same district prefix. The Census 2024 SLD update has no Alaska change, so `cb_2024_02_sldl_500k` is the 2022 plan.
- **TLS:** elections.alaska.gov serves the wrong intermediate certificate. I fetched it with a CA bundle that adds the GlobalSign GCC R46 OV TLS CA 2025.
- **sen_prev per district is an ESTIMATE:** the 2020 race was counted on the old 2013 districts.
  1. Each old district's absentee, early and question votes (56% of in-district votes) were spread over that district's precincts in proportion to each precinct's election-day votes for the same candidate.
  2. Each 2020 precinct is the Census 2020 VTD with the same code; all 441 matched, so the fallback was used 0%. Each VTD was split across the new districts by the voting-age population (PL 94-171) of its blocks, using the Census 2022 SLDL block equivalency file (`sldl_2022.zip`).
  3. Integers were assigned by largest remainder, so the sums are exact.
  4. 91 precincts, holding 11.8% of votes, were split between districts.
  5. Compared with a plain old-district to new-district crosswalk, the margin moves by a median of 2.4 points. The largest move is 19 points in HD34, where the precinct method is closer to the 2024 result.
  6. Show it on air as "2020 result re-allocated to today's districts". The statewide figures are exact.

**KS** (Kansas Secretary of State)
- **Sources:** `sos.ks.gov/elections/24elec/2024-Presidential-Results.xlsx`, `20elec/2020_General_Election_US_Senate_results_by_precinct.xlsx` and `22elec/2022-General-Election-Turnout-Information.xlsx` (total ballots cast). Statewide totals come from the Official Vote Totals PDFs.
- **2020 write-ins:** unregistered write-ins (Shawnee 94, Sedgwick 242, Wyandotte 120) are not in the certified canvass, so they are excluded.
- **Errors in the 2022 turnout file:**
  - Stevens and Sumner are transposed; I swapped them back to 1,403 and 7,979.
  - Washington (2,002 ballots against 2,257 governor votes) and Montgomery (11,168 ballots against 9,611) disagree with their own certified governor votes. I replaced them with EAC EAVS 2022 item F1a: 2,266 and 9,679.
  - The statewide figure stays the official 1,020,208. The resulting residual of 1,225 is recorded in `not_in_units.turnout2022`. It is a reconciliation residual, not a ballot category.

**OH**
- **Blocked:** ohiosos.gov returns 403 behind a Cloudflare bot check, which I did not try to bypass. All county data therefore come from **MEDSL** precinct returns (CC0), which republish the SOS official precinct canvass:
  - `MEDSL/2024-elections-official/individual_states/oh24.zip`
  - `MEDSL/2022-elections-official/individual_states/2022-oh-local-precinct-general.zip` (Senate, and "BALLOTS COUNTED" for turnout)
- **Statewide:** checked against the FEC. The turnout of 4,201,368 equals the SOS certification figure and matches EAVS in all 88 counties.
- **Write-ins:** the 2,771 certified 2024 presidential write-ins are not broken out by county, so they are in `not_in_units.pres2024.other`.
- **Upgrade path:** if ohiosos.gov becomes reachable, its county canvass xlsx can replace MEDSL.

**MI**
- **Blocked:** michigan.gov and MVIC return 403, and mielections.us times out. I used Internet Archive captures of the SOS data files:
  - `mielections.us/election/results/DATA/2020GEN_MI_CENR_BY_COUNTY.xls` (OFFICIAL, 11/23/2020)
  - `.../2022GEN_MI_CENR_TURNOUT.xls` (ballots cast, OFFICIAL, 12/22/2022)
- **pres2024:** no archived official county file exists, so county numbers come from **MEDSL** `mi24.zip` precinct returns (CC0, from the SOS precinct results). Statewide matches the certified totals exactly.
- **Unit sums:** county sums equal statewide exactly.

**ME** (Secretary of State, Bureau of Corporations, Elections & Commissions)
- **Access:** maine.gov returns 403. I used the Maine State Law and Legislative Reference Library's mirror of SOS returns (`lldc.mainelegislature.org/Open/Elections/Returns/...`) and an Internet Archive capture.
- **pres2024:** the SOS file corrected on 2024-12-05, `President and Vice President FINAL-Corrected 20241205.xlsx`. The version first posted had Harris 435,351 and Trump 377,837.
- **sen_prev:** `2020/20201103/elec_20201103ad.xlsx`, the first round. Collins had 50.98%, so no ranked-choice rounds were run.
- **turnout2022:** total ballots cast from the 2022 governor tabulation, `2022/20221108/elec_20221108f.xlsx`. No separate per-town turnout file was found.
- **Method:** towns, including unorganized territories, were aggregated to counties by the county code. Each county was verified against the SOS county subtotal.
- **Overseas bucket:** the statewide-only "STATE UOCAVA" line goes in `not_in_units`: pres2024 6,569 votes, sen_prev 5,648 and turnout2022 1,845 ballots.
- **Coding fix:** "T3 ND Twp" (4 ballots in 2022) is coded PEN but is a Hancock township, and the SOS Hancock subtotal includes it, so it is counted in Hancock.

## Geometry

**Source.** US Census Bureau cartographic boundary files, 2024 vintage (public domain):
- `cb_2024_us_state_20m` (Puerto Rico dropped)
- `cb_2024_us_county_500k`
- `cb_2024_02_sldl_500k` (Alaska SLDL, LSY 2024)

The cb files are already clipped to the coastline and Great Lakes shoreline.

**Method.** The tooling is in a throwaway venv in the session scratchpad:
- **Simplification:** build a topology of shared arcs with the `topojson` package, then run Douglas-Peucker on each arc once. Neighbouring units therefore keep identical borders.
- **Tolerance per arc:** `clamp(0.01 * sqrt(area of the smallest unit on the arc), 0.0002-0.0005 deg, cap)`. The cap is about a quarter pixel when the state fills 1920x1080: TX 0.0025, MI 0.0016, ME 0.0012, KS/OH 0.001, AK 0.008 deg. Small rings are capped at 0.1 * sqrt(ring area) so they keep their shape.
- **Detail for insets:** because of this, urban Anchorage, Fairbanks and Juneau house districts keep enough detail for an inset (checked at about 30x zoom).
- **Islands:** only true islands are dropped, meaning parts that touch no other unit, and only below 3e-4 deg² in AK or about 1e-5 deg² elsewhere. Every unit keeps its largest part.
- **Rounding:** coordinates are rounded to 4 decimals and snapped to that grid with `shapely.set_precision`, which keeps the output valid.

**Winding: exterior rings are clockwise**, the d3-geo spherical convention (the reverse of RFC 7946). With counter-clockwise rings d3 would fill the whole globe. The test checks this.

**Aleutians:** the western islands are kept as separate polygons at longitudes +172 to +180, which d3 handles. For `AK.json`, fit a projection such as `geoConicEqualArea().rotate([154,0])`, not a plain equirectangular one.

**Quality.** I rendered every file to PNG and inspected it (full state at 1920x1080, plus Anchorage, Fairbanks and Houston zooms). There are no visible gaps or slivers.
- **Measured defects:** one in Texas, at the Camp/Franklin/Wood tri-junction (Lake Cypress Springs), of about 1e-6 deg² (about 0.005 km², far below a pixel). It comes from a source vertex that only one neighbour has, so that bit of border was not detected as shared and the two sides were simplified separately. Everything else has zero overlap and zero holes.
- **KS and OH are under 100 KB** because their county lines are mostly straight. More vertices would add nothing visible.
- **Alaska inset:** on the state view, the 16 Anchorage districts are 1-3 px each, so the page needs an Anchorage/Mat-Su inset (and Fairbanks, Juneau).

## Senate holdovers (`data/election/senate_holdovers.json`)

Source: senate.gov `senators_cfm.xml`, fetched 2026-11-02 with Last-Modified 2026-10-08, plus the Party Division and Appointed Senators pages.
- **Composition is still 53 R, 45 D and 2 I** (Sanders, King, caucusing with D), with 0 vacancies.
- **Membership changes this Congress, all Republican to Republican:**
  - Husted (OH) replaced Vance, 2025-01-21.
  - Moody (FL) replaced Rubio, 2025-01-21.
  - Alan Armstrong (OK) replaced Markwayne Mullin, who resigned 2026-03-23 to become Homeland Security Secretary; sworn in 2026-03-24. He is barred by state law from running.
  - Darline Graham (SC) replaced Lindsey Graham, who died 2026-07-11; sworn in 2026-07-14.
- **Holdovers:** 65 seats, 31 R, 32 D and 2 I.
- **Up in 2026:** 35 seats, 22 R and 13 D: the 33 Class II seats plus the FL and OH Class III specials.
- **Sourcing caveat:** the dates of Mullin's resignation and Graham's death come from press reports compiled on Wikipedia, and senate.gov confirms both appointments. The session's web-search budget ran out, so I could not check them further.

Out of scope, for whoever builds `races.json`: the same Wikipedia snapshot says Cornyn and Cassidy lost renomination and Maine Democrats replaced Platner. I have not verified this. The TX `sen_prev` is still the seat's 2020 race.

## Problems / caveats
1. **OH and MI 2024 county data come from MEDSL**, not a state-published county file, because the state sites block automated clients. Statewide totals are exact against the certified results.
2. **AK `sen_prev` per district is an estimate** (see above).
3. **Turnout definitions differ by state:**
   - TX uses 2022 governor votes.
   - ME uses the governor tabulation's total ballots cast.
   - KS has two counties replaced from EAVS.
   - AK, KS, OH and MI use official ballots cast.
4. **Rebuild scripts are not in the repo.** They live in the session scratchpad (`scripts/{TX,AK,KSOH,MIME}/`, `scripts/build_geo.py`, `scripts/build_holdovers.py`), with renders in `work/png/`.

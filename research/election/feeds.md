# Election-night results feeds: official sources for the six featured 2026 Senate races

Researched and tested 2026-11-02 (the day before the election). Code: `src/election/feeds/` (`<st>.py`, `common.py`,
`fips.py`, `certs/`). Tests: `tests/election/test_feeds.py` (22 offline tests, all passing) with fixtures in
`tests/election/fixtures/`. Output schema: "Live results" in `docs/ELECTION.md`. AK uses `unit_type: "house_district"`,
the same value as `data/election/baseline/AK.json`.

```
cd src && python -m election.feeds ALL --out output/election/live/            # once
cd src && python -m election.feeds TX OH --out output/election/live/ --loop 180
```

Relative `--out` paths resolve against the repo root. Each `<ST>.json` is written atomically (temp file + rename,
mode per umask, not mkstemp's 0600). A failed fetch keeps the last good file and prints `<ST>: <ErrorType>: <reason>`. The error types are
`SourceBlocked` (bot challenge, WAF or unreachable host; never retried or bypassed), `NotPublished` (the 2026 general
file is not at the expected place yet, or the file there is another election), `TestData` (the file is flagged as a
test; `--allow-test` overrides) and `ParseError`.

Only official state publications are used. Nothing comes from AP, DDHQ, networks or newspapers.

## Live check on 2026-11-02 ~01:45 UTC

| state | result of `python -m election.feeds ALL` |
|---|---|
| TX | ok: the 2026 general zero file. 254 counties, 0 of 9,900 precincts, Paxton / Talarico / Brown + write-ins |
| AK | NotPublished: `/enr26/results/` still holds the Aug 18 primary. The summary PDF says "2026 PRIMARY ELECTION" |
| KS | SourceBlocked: ent.sos.ks.gov answers with a Cloudflare "I'm Under Attack" JS challenge (HTTP 403) |
| ME | SourceBlocked: www.maine.gov answers "403 Request blocked" from CloudFront on every path, robots.txt included |
| OH | TestData: the 2026 general file is live with `IsTest="true"` and zeros (88 counties, 8,834 precincts). Works with `--allow-test` |
| MI | SourceBlocked: mvic.sos.state.mi.us answers with a Cloudflare managed challenge. mielections.us times out (TCP) |

Shared HTTP behaviour (`common.get`):

* User-Agent `election-results-desk/0.1 (independent livestream)`, with no email address.
* (10 s, 60 s) timeouts and 2 retries with backoff on connection errors, 429 and 5xx (Retry-After is honoured).
* At least 2 s between requests to the same host.
* ETag / If-Modified-Since conditional GETs, backed by a disk cache in `output/election/cache/http`.
* `ELECTION_RAW_DIR` saves every downloaded body for post-mortems.

TLS verification is never turned off. Alaska gets one extra verified intermediate (see AK).

---

## TX: Texas Secretary of State (Civix "IVIS" ENR)

* **Source**: Texas SOS Election Night Returns, run by Civix since 2025 at
  `https://goelect.txelections.civixapps.com/ivis-enr-ui/`. The old `results.texas-election.com` is frozen at 2024 and
  sits behind a Cloudflare challenge.
* **Endpoints**: public JSON with no authentication. Each section is base64-wrapped JSON (`{"Section": "<base64>"}`).
  * `…/api-ivis-system/api/s3/enr/electionConstants` lists every election by year and type.
  * `…/api/s3/enr/election/<id>` holds the statewide data: `Home` (LastUpdatedTime, Central time; counties,
    precincts and polling places reporting) and `Federal.Races[]`. Each candidate has V (votes), EV (early votes),
    P (party) and LN (last name).
  * `…/api/s3/enr/election/countyInfo/<id>` holds all 254 counties × every race. Counties are keyed 1..254 in SOS
    alphabetical order, which is **not** FIPS order around the "Mc" names, so FIPS comes from the county name. Each
    race also carries per-county `PR`/`TP` (precincts reporting/total).
* **2026 readiness**: listed and published. Ids:
  * 53815 = "2026 NOVEMBER GENERAL ELECTION" (zero file, LastUpdated Oct 29 22:13 CT). The race is "U. S. SENATOR"
    (race id 5075): Ken Paxton (REP), James Talarico (DEM), Ted Brown (LIB), plus 4 declared write-ins.
  * Others: 58315 / 58314 (GOP / Dem primary runoffs, May 26); 53813 / 53814 (March 3 primaries).
  * Discovery: `electionConstants["electionInfo"]["2026"]["GE"]`, where the name matches "NOVEMBER GENERAL".
    Override with `TX_ELECTION_ID`.
* **Units**: 254 counties.
* **Precincts**: race-level PR/TP, summed (9,900 in the general). The site also publishes polling places reporting
  (`PollingReporting`, 5,302 locations). The adapter does not use that figure.
* **Write-ins**: declared write-ins are listed with party "W" and summed into `writein`.
* **Cadence**: the state page refreshes every 5 min (`RefreshTime: 5`). The SOS says county returns update every
  5 min until 100% are in.
  * The responses are no-cache with no ETag. One poll is ~1.6 MB (election) + ~4.2 MB (countyInfo) uncompressed, so poll every
    2–3 min.
* **Terms**: robots.txt allows `*` but carries `Content-Signal: search=yes, ai-train=no, use=reference`. Our use is
  live reference display, not AI training. ClaudeBot, CCBot and other crawlers are disallowed by name, and we are not
  those agents.
  * The SOS sells registered media an XML newsfeed by SFTP ($250 in 2022; registration closed in September). We do
    not have it.
  * The host is fronted by Cloudflare. It does not challenge the API today.
* **Test status**: tested. The fixture is the 2026 GOP runoff (Cornyn 503,438 v Paxton 888,196; total 1,391,634;
  9,534/9,534 precincts; Harris 52,041 / 93,872). The 2026 general zero file is a second fixture (structure,
  write-ins). Discovery and a full offline `fetch` are also tested, and a live fetch of 53815 works.
* **Risks**:
  * Cloudflare could start challenging on election night: the old portal already does.
  * The payload is large.
  * The base64 wrapper and field names are vendor-internal and could change without notice.
  * **Fallbacks**: county official ENR pages for the big counties (Harris, Dallas, Tarrant, Bexar, Travis). These
    were not verified here because the search budget ran out.

## AK: Alaska Division of Elections

* **Source**: Division of Elections results pages on `www.elections.alaska.gov`. The live ENR files are served from
  S3 under `/enr26/results/` and later archived under `/results/<YY><TYPE>/`.
* **Endpoints**:
  * `GA_ENR_Precinct_State_of_Alaska.csv`: the ES&S "GA ENR" export, one row per precinct × contest × candidate,
    with ballots/votes by vote type. This is the machine-readable source. It is a CSV, not a PDF/HTML-only summary.
  * `ElectionSummaryReportRPT.pdf`: statewide summary, with "Precincts Reported: X of Y" per contest, a title line
    and a timestamp.
  * Discovery: links under the `<h2>2026 General Election – November 3, 2026</h2>` heading on
    `/election-results/`. The fallback is the `/enr26/results/` paths. Overrides: `AK_CSV_URL` / `AK_PDF_URL`.
* **2026 readiness**: the general's section exists, but only ballot-count tables are posted so far (Combined Ballot
  Report, 113,301 ballots received as of Nov 1).
  * `/enr26/results/` still holds the **primary** (Last-Modified Aug 31). The adapter refuses it: the PDF title must
    match "2026 GENERAL ELECTION". With no PDF, the CSV must be modified on or after Nov 3.
  * Expect the files to be replaced in place after polls close: 8 pm AKST = 05:00 UTC Wed; the Aleutians close at
    06:00 UTC.
  * Senate general candidates: Mary Peltola (D), Dan S. Sullivan (R), Daniel J. Sullivan Jr., plus others and
    certified write-ins.
  * Two Sullivans are on the ballot. Explicit key overrides set `sullivan` = Dan S. Sullivan and `sullivan_jr` =
    Daniel J. Sullivan Jr.
* **Units**: `AK-HD01..40`.
  * Precinct ids "NN-xxx" → HD NN.
  * "District N - Absentee / Early Voting / Question" rows → HD N.
  * "HD99 Fed Overseas Absentee" → statewide only, so the statewide total exceeds the sum of the HDs.
* **Precincts**: statewide figure from the summary PDF (pdfplumber, with fallback to the project's
  `desk.pdftext`). `Reporting_flag` is 0 on every row of the archived files, so per-HD precincts are null unless the
  flags start being used.
* **Write-ins**: rows with `Candidate_Type == "W"` or named "Write-in" are summed into `writein`.
* **RCV**: the U.S. Senate general uses ranked-choice voting, so election-night numbers are **first choices**. The
  Division runs the RCV tabulation after the count closes (about 15 days later).
* **Cadence**: unknown. Late ballots are counted for days. Poll every 5 min: S3 sends ETag and Last-Modified.
* **Terms**: robots.txt only disallows `/wp-admin/`. The server sends the wrong TLS intermediate:
  `certs/globalsign_gcc_r46_ov_tls_ca_2025.pem` (fetched from GlobalSign's AIA URL, verified against GlobalSign
  Root R46 in certifi, SHA-256 D1:60:E2:DE:…:40:63:F9) is appended to certifi for this host.
* **Test status**: tested.
  * The fixture is the 2026 primary CSV, U.S. Senator rows only: 166,004 total, which equals the official summary.
    Peltola 82,244, Sullivan 68,726, Sullivan Jr. 4,107.
  * Also tested: summary-text parsing, HD mapping, write-ins, discovery, and the "still the primary" guard. A live
    fetch correctly returns NotPublished.
* **Risks**:
  * The general file may be posted under another path or name. Discovery from the results page covers that; set
    `AK_CSV_URL` if the page lags.
  * The PDF layout could change, which would lose only the precinct count.
  * **Fallbacks**: the Division's Combined Ballot Report HTML (ballot counts only), and the per-HD PDFs
    (`/enr26/results/HD<n>.pdf`).

## KS: Kansas Secretary of State ("Unofficial Kansas Election Results", ent.sos.ks.gov)

* **Source**: static HTML generated by the SOS. There is no JSON/XML/CSV feed. Precinct-level `.xlsx` files are
  posted only after the canvass.
* **Endpoints**: `https://ent.sos.ks.gov/national.html` (federal races) and `https://ent.sos.ks.gov/kssos_ent.html`
  (all races). One page holds everything:
  * each race block (`div.race`, `<h3>` title) has the statewide totals and "Precincts Reporting: X of Y";
  * a `<map>` of 105 `<area title="…">` tooltips holds each county's results, e.g. "Allen County / 22 of 22
    precincts reporting / R-Roger Marshall 1,191".
  * Party is a name prefix (R-, D-, L-, i-) in generals. In primaries it comes from the title ("United States
    Senate (R)").
* **2026 readiness**: unknown, because the page is blocked from here. The last archived copy of the root page (Oct 15)
  still showed the Aug 4 primary.
  * The general's race title should be exactly "United States Senate", which is the default `KS_RACE`.
  * Pages whose timestamp is earlier than 2026-11-03 are refused (`KS_MIN_DATE`).
* **Units**: 105 counties.
* **Precincts**: yes, statewide and per county.
* **Write-ins**: not shown in the 2024 or 2026 pages. They would be summed if they appear.
* **Cadence**: the page carries a "Last Updated" stamp (Central time). The update interval is not published.
* **Terms**:
  * `sos.ks.gov/robots.txt` disallows `/ent/` and `/api/` on the main host. ent.sos.ks.gov has no robots.txt (404).
  * **ent.sos.ks.gov is behind Cloudflare in "I'm Under Attack" mode**. Every request from this client gets a 403 JS
    challenge, which we detect and do not bypass (the adapter makes one request, then stops).
* **Test status**: parser tested against trimmed copies of the official pages, retrieved from the Internet Archive.
  This was the only way to get the files.
  * 2026 primary U.S. Senate (R): Marshall 267,972 v Naramore 67,496; 4,150/4,150 precincts; Johnson 53,216 / 16,831.
  * 2024 general President: party prefixes; 1,281,725 = the sum of the 105 counties.
  * The live fetch is **blocked**.
* **Risks**: **high**. Unless the challenge is lifted on election night, there is no automated official source.
  * Options: ask the KS SOS Elections Division (800-262-VOTE) to allowlist the desk's IP/UA, or run the fetch from
    a network or browser the challenge accepts. The second option is the user's call.
  * **Fallbacks**: county election offices' official pages (Johnson, Sedgwick, Shawnee, Wyandotte, Douglas). Not
    verified here (search budget exhausted).
  * Narration may cite news reports, with attribution, but they are not used as data.

## ME: Maine Secretary of State (Bureau of Corporations, Elections and Commissions)

* **No official machine-readable election-night feed** (the suspicion is confirmed). Maine publishes **no statewide
  unofficial results on election night**. Municipal clerks report to the SOS, which posts Excel tabulations by
  municipality on `…/election-results-data/election-results-<year>` after the election. The SOS says official
  results are posted within 20 days.
  * Evidence from 2024: the earliest archived general-election files are "US Senator FINAL.xlsx" (Dec 2024) and
    "Nov24 CG2 1st Choices.xlsx". No election-night files exist.
  * RCV contests get a "1st Choice results reported by the municipalities" file before the central RCV tabulation.
  * The U.S. Senate general is an RCV race.
* **Best official option (implemented)**: `me.py` parses the SOS tabulation `.xlsx` and aggregates towns to the 16
  counties.
  * Layout: COUNTY code | MUNICIPALITY | candidate columns ("Last, First"), with residence and party rows below,
    then BLANK and TBC. "XXX Total" rows are skipped, "STATE UOCAVA" counts statewide only, and "STATEWIDE TOTALS"
    is cross-checked.
  * Towns are kept under `towns`, with `{id: "<county fips>-<slug>", name, county, votes, total}`.
  * Discovery: `.xlsx` links matching "U.S. Senat…" on the 2026 results page. Party-primary files ("Dem/Rep") are
    excluded and "1st Choice" files are preferred. Override with `ME_XLSX_URL`.
* **Precincts**: null (not published). **Write-ins**: a "Write-in/Others" column would be summed. It is absent in
  2024.
* **Terms / access**: www.maine.gov (CloudFront) returns `403 Request blocked` to this client on every path,
  robots.txt included, so the live fetch is **blocked** here. www11.maine.gov serves robots.txt (only
  `/sos/kids/search/node` is disallowed under /sos) but redirects everything else to www.
* **Test status**: tested against the official 2024 "US Senator FINAL.xlsx" (from the Internet Archive): King
  427,331, Kouzounas 284,338, Costello 88,891, Cherry 20,222. Town sums equal the official STATEWIDE TOTALS minus
  UOCAVA. Discovery and the CloudFront-block path are also tested.
* **Risks / fallbacks**: expect **no official Maine numbers on election night**.
  * Fallbacks: municipal clerks' own official postings for the largest cities (Portland, Lewiston, Bangor, South
    Portland, Auburn). Not verified.
  * News reports (Maine Public, BDN, Press Herald) may be cited **only** as attributed narration, never as data.
  * The SOS 1st-choice file appears days later. The `st_votes_left` visual should show "not yet reported".

## OH: Ohio Secretary of State ("Ohio Decides", liveresults.ohiosos.gov)

* **Source / endpoint**: `https://liveresults.ohiosos.gov/Api/v1/download?filename=VSSC1622XmlFileBlob`. This is
  an ElectionReport in Ohio's implementation of the draft NIST SP 1500-100 / IEEE 1622 format, documented at
  `/Content/PDF/P1622Documentation.pdf`.
  * Each contest has one statewide `VoteCounts` plus one per county GpUnit.
  * County GpUnits carry `SubUnitsReported` / `TotalSubUnits` (precincts) and `VotersRegistered`.
  * Also available, unused: `/Api/v1/Contest/GetElectionSummaryCsv` (ballots cast by county) and the JSON calls
    behind the page (`/Api/v1/Contest/GetContestDetailsObject`, …).
* **2026 readiness**: **published**. The file is the 2026-11-03 General, contest "U.S. Senator": Sherrod Brown (DEM),
  Jon Husted (REP), Greg Levy (other party), William Redpath (LIB), plus 3 write-ins.
  * It is flagged `IsTest="true"`, `Status="UnofficialPartial"`, with all zeros. The adapter refuses `IsTest` files
    unless `--allow-test`, and checks the election date.
* **Units**: 88 counties. **Precincts**: yes, 8,834 statewide.
* **Write-ins**: the site says write-in results are not reported on election night. The `writein` line is shown
  only when non-zero.
* **Cadence**: `GeneratedDate` moved 01:18 → 01:42 UTC while we watched. The file is ~0.1 MB compressed, with
  `Cache-Control: max-age=15`, ETag and Last-Modified, so a conditional poll every 60–120 s is cheap.
* **Terms**: robots.txt is `User-agent: *` with no disallows. The host is fronted by Cloudflare, with no challenge
  seen.
* **Test status**:
  * Tested against the live 2026 general test file (structure, parties, 88 counties, precincts, test and date
    guards).
  * Arithmetic is tested by filling made-up counts into that file inside the test (labelled synthetic).
  * **No past election in this format is retrievable**: the endpoint serves only the current election and none is
    archived, so no real-number fixture exists.
* **Risks**: the first real numbers will be seen live. Watch for the `IsTest` flag flipping, and for a Status of
  "UnofficialComplete"/"Official". **Fallbacks**: county boards' result pages (the feed lists each board's URL in
  `ContactInformation/Uri`, e.g. `https://www.boe.ohio.gov/adams/election-info/election-results/`).

## MI: Michigan Secretary of State / Bureau of Elections

* **Source**: michigan.gov's "Election results and data" page links the 2026 general's results to
  `https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-3-2026`. From the page code (a 2025
  archive copy):
  * the elections are listed in `<select id="ElectionDateId">`, e.g. 699 = "11/5/2024 STATE GENERAL";
  * county results load from `/VoteHistory/GetCountyVoteRecords?electionId=<id>` (an HTML fragment);
  * precinct results load from `/VoteHistory/GetPrecinctInfo?electionId=<id>&countyCode=<1..83>`;
  * a bulk file is at `/VoteHistory/GetElectionResultFile?electionId=<id>`.
  * The older election-night site's pattern is `https://mielections.us/election/results/<YYYY><CODE>_CENR.html`
    (michigan.gov still links `2016SG1_CENR.html`), so 2026 would be `2026GEN_CENR.html`.
* **2026 readiness**: unknown, because the source is blocked from here.
* **Access**:
  * MVIC returns a **Cloudflare managed challenge** (403) on every path, including robots.txt, and WebFetch is also
    refused.
  * `mielections.us` does not accept TCP connections from this network.
  * The Internet Archive holds no copy of the results fragment or file. So **the county-results format could not be
    observed**.
* **What is implemented**: `mi.py` discovers the election id from the MVIC page and requests the county fragment. If
  a body comes back (another network, or the challenge lifted), it saves the body to `output/election/raw/MI/` and
  raises `ParseError`, so the parser can be written against the real format quickly. **It never returns guessed
  numbers.**
* **Units / precincts / write-ins / cadence**: unknown.
* **Test status**: discovery tested (699/698 from the archived selector) and the blocked path tested. **No results
  parser, so not tested on results.**
* **Risks / fallbacks**: **high**.
  * Run the fetch from the broadcast host (EC2), whose network may differ, as soon as possible on election day to
    capture a sample. Or ask the Bureau of Elections for access.
  * County clerks' official result pages are linked from michigan.gov ("Candidate listings and election results by
    county"): Wayne, Oakland, Macomb, Kent and others; Lake County uses Enhanced Voting.
  * Oakland's Clarity election list is empty, so Oakland no longer uses Clarity.
  * News reports may be used only as attributed narration.

---

## Summary

| state | official source | format | county-level | 2026 endpoint known | tested |
|---|---|---|---|---|---|
| TX | SOS Civix ENR API | base64 JSON | yes (254) | yes, id 53815, zero file live | yes: 2026 runoff + general zero file; live OK |
| AK | Division of Elections | CSV (+ summary PDF) | HD01–40 | path known (`/enr26/results/`), not yet replaced | yes: 2026 primary; live guard OK |
| KS | SOS ent.sos.ks.gov | static HTML | yes (105) | yes (national.html / kssos_ent.html) | parser yes (2026 primary, 2024 general); live blocked |
| ME | SOS tabulations | XLSX by town | yes (towns → 16) | page known, file name unknown; no election-night file | parser yes (2024 Senate); live blocked |
| OH | SOS Ohio Decides | NIST 1500-100 XML | yes (88) | yes, test file live | structure yes (2026 test file); no real-number fixture |
| MI | SOS MVIC | unknown (HTML fragment) | likely | URL pattern known, id not discoverable from here | discovery only; no parser |

## Notes on method

* Requests were spaced by several seconds, and each state saw a few dozen requests at most. Bot challenges were
  never bypassed. One attempt to probe the old Texas portal with a browser UA was denied by the harness and not repeated.
* KS and ME fixtures and the MI selector came from Internet Archive copies of the official pages. The archive was
  only the transport for official content and is not a data source at runtime.
* The web search budget ran out during the Michigan research. County-level fallbacks are listed from the official
  michigan.gov county page or general knowledge, and are marked as unverified where they could not be checked.
* New env dependencies (installed into `ai-livestream` and not yet in `requirements/`): `openpyxl` (ME; required)
  and `pdfplumber` (AK; optional, falls back to `desk.pdftext`).

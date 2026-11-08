# 2026 U.S. Senate candidates: sources and verification notes

Companion to `data/election/races.json`. Compiled 2026-11-02 (UTC), the day before the election. Election day is Tue 2026-11-03.
All times are ET (UTC-5; daylight saving time ended Nov 1).

## How this was verified

- **Race list and nominees, all 35 races.** Every nominee was checked against at least two independent compilations:
  - the Wikipedia article for each race, raw wikitext fetched 2026-11-02;
  - The Green Papers state pages (thegreenpapers.com/G26/XX, fetched 2026-11-02), which track certified candidate lists and filings.
- **Incumbents and party balance** come from senate.gov: the Class I, II and III lists and the party-division page, fetched 2026-11-02. The Class II list already shows Alan Armstrong (R-OK) and Darline Graham (R-SC).
- **Official state candidate lists** were read where reachable:
  - Colorado: coloradosos.gov general candidates, certified Sept 4.
  - Delaware: elections.delaware.gov general list.
  - Montana: candidatefiling.mt.gov primary filing list, which shows Daines "Withdrawn" and Alme "Nominated".
  - New Mexico: the primary list, which shows Marker as a write-in.
  - Featured states: Texas SOS sample ballot; Alaska Division of Elections; Kansas SOS; Maine SOS final list (via Wayback captures); Franklin County OH certified list; Michigan official candidate listing of Oct 27.
- **Key late changes** were confirmed in news:
  - NBC News on Lindsey Graham's death (2026-07-11).
  - WOWT/KOLN (1011now) on Nebraska Democrat Cindy Burbank's removal from the ballot (2026-07-21).
  - Nebraska.tv on the Nebraska Democratic Party backing Dan Osborn.
- **Fundraising for the inclusion decisions** (FEC receipts through 2026-10-14) came from the FEC API (api.open.fec.gov, read for CO, SD, ID, IL, NH, NJ, OK, OR, NC and MI) and from The Green Papers' FEC summaries. These figures are only for deciding who gets a card or a nominee slot. **Never show them on screen.**
- **Access limits this session:**
  - Ballotpedia returned a bot challenge (curl) or an empty page (WebFetch).
  - bioguide.congress.gov, maine.gov, ohiosos.gov and several news sites returned 403.
  - The shared web-search budget of 200 searches ran out partway through. Later checks were direct fetches of known URLs only, so the very latest news (Nov 1-2) may be incomplete. Re-check the morning of Nov 3: the AP race pages, each state's election-night site, and for Alaska any appeal of the Nov 1 ruling.

## Senate before the election

- **Party division** (senate.gov, 119th Congress, 2nd session): **53 Republicans, 45 Democrats, 2 independents.** The independents are Angus King (ME) and Bernie Sanders (VT), and both caucus with the Democrats.
  - CNA puts it as 共和黨占53席，民主黨45席，2席無黨籍屬民主黨團.
- **Seats up: 35.** These are the 33 Class II seats plus 2 Class III specials (FL, OH).
  - **Republicans are defending 22:** 20 Class II seats plus Florida and Ohio.
  - **Democrats are defending 13.**
  - Independents are defending none.
- **Seats not up: 65** (31 R, 32 D, 2 I), listed in `holdovers`.
- **Open seats: 13**, meaning no incumbent is on the ballot. 9 are Republican-held: AL, IA, KY, LA, MT, NC, OK, TX, WY. 4 are Democratic-held: IL, MI, MN, NH.
- **Incumbents on the ballot: 22.** 3 of them are appointees: Moody (FL), Husted (OH) and Darline Graham (SC). Alan Armstrong (OK) is also an appointee but is barred by state law from running.
- **Majority:** 51 seats, or 50 plus the tie-breaking vote of the vice president (JD Vance, Republican). With 47 seats in their caucus, Democrats need a net gain of 4 seats for 51; this is arithmetic, not a forecast.

## What changed during the cycle (verify on air with attribution)

**Deaths and appointments**
- **South Carolina.** Sen. Lindsey Graham (R) won the 2026-06-09 primary and died on 2026-07-11, aged 71 (NBC News). Gov. Henry McMaster appointed his sister Darline Graham (Darline Graham Nordone) on 2026-07-13. She won the special Republican primary runoff on 2026-08-25 against Rep. Ralph Norman (52.5% per The Green Papers; Wikipedia gives 52%/52.5%). Her opponent is Annie Andrews (D).
- **Oklahoma.** Markwayne Mullin resigned in March 2026 to become Secretary of Homeland Security, and Alan Armstrong (R) was appointed. Dates differ by source: Wikipedia says Mullin resigned 2026-03-23 and Armstrong was sworn in 2026-03-24; The Green Papers puts both on 2026-03-24. Oklahoma law bars the appointee from running. The nominees are Kevin Hern (R) and N'Kiyla Jasmine Thomas (D), who won the 2026-08-25 runoff.

**Incumbents who lost renomination**
- **Texas.** John Cornyn lost the 2026-05-26 Republican runoff to Ken Paxton.
- **Louisiana.** Bill Cassidy finished third in the 2026-05-16 closed Republican primary. Julia Letlow won the 2026-06-27 runoff. This is the first Louisiana Senate race under closed party primaries; the general election is decided by plurality.

**Late withdrawals and replacements**
- **Montana.** Steve Daines withdrew on the 2026-03-04 filing deadline. Kurt Alme (R) filed the same day.
- **Maine.** Democratic primary winner Graham Platner announced his withdrawal on 07-08 and filed it on 07-10. A state convention picked Troy Jackson on 07-25, and the SOS received the nomination 07-27.
- **Nebraska.** Democratic nominee Cindy Burbank declined the nomination and was removed from the ballot (SOS confirmation 07-21). No Democrat is on the ballot. The party had announced in July 2025 that it backs independent Dan Osborn. A primary loser's suit to force a replacement was dismissed on 2026-08-26 (Wikipedia, citing a Courthouse News copy of the order; not opened). Legal Marijuana Now nominee Mike Marvin stayed on the ballot and on 08-21 urged his supporters to back Osborn (The Green Papers).
- **Idaho.** Democratic nominee David Roth withdrew in late July after Todd Achilles, a former Democratic state representative, entered the race as an independent. Source: Wikipedia, citing the Idaho Capital Sun of 07-28; that article returned 403 here and was not opened.
- **South Dakota.** Democratic nominee Julian Beaudion withdrew on 2026-08-04. Brian Bengs, the 2022 Democratic nominee, runs as an independent. Source: Wikipedia, citing the Washington Post of 08-04; that article returned 403 here and was not opened. The FEC lists Bengs as IND.
- **Alaska.** Fourth-place primary finisher David Leslie (D) withdrew on 08-31, which moved Gerald Heikes (R) onto the ballot. Courts restored Daniel J. Sullivan Jr. to the ballot in late June. A federal suit over certification was dismissed on Nov 1 (see the Alaska notes).
- **Michigan.** Mallory McMorrow withdrew before the 08-04 primary but stayed on the primary ballot. Abdul El-Sayed beat Haley Stevens narrowly.

**Primary results to note**
- **Florida.** Angie Nixon beat Alex Vindman in the 08-18 Democratic primary.
- **New Mexico.** Larry Marker won the Republican nomination as a write-in, because no Republican qualified for the primary ballot.
- **Georgia.** No Libertarian is on the ballot (AJC, July 2026). The Dec 1 general-election runoff applies only if no one exceeds 50%.

## Inclusion rule (who is a "nominee" and who gets a card)

- **`nominees`:** the Democratic and Republican nominees, plus any independent or third-party candidate on the printed ballot who either:
  - raised more than about $1M (FEC receipts through 2026-10-14), or
  - is the only significant non-Republican/non-Democratic opponent, because the Democratic nominee withdrew (NE, ID, SD).

  This works out to:

  | candidate | state | FEC receipts | note |
  |---|---|---|---|
  | Dan Osborn (IND) | NE | ~$11.0M | |
  | Seth Bodnar (IND) | MT | ~$4.9M | also on the ballot with Democrat Alani Bankhead |
  | Bob Chew (Forward Party) | CO | ~$3.6M | FEC; the Republican nominee had ~$0.14M |
  | Todd Achilles (IND) | ID | ~$1.9M | |
  | Brian Bengs (IND) | SD | ~$1.9M | |

  No polls were used for the national list because no polling source was checked this session.
- **Below the bar** (listed in `other_candidates`):
  - Shiva Ayyadurai (MA, ~$0.24M) and Joe Tache (MA, ~$0.29M)
  - Ty Pinkins (MS, ~$0.10M)
  - Michael Bahry (RI, ~$0.13M)
  - Kyle Austin (MT, ~$0.26M)
  - Greg Levy (OH, ~$0.13M)
  - all others, under $0.1M or with no FEC data
- **Featured cards:** only the D and R candidates, or in Alaska the two leading top-four finishers. Every other printed name is under `also_on_ballot`. The evidence (polls and FEC figures) is in each state's notes below.
- **Inclusion evidence is internal.** Polls, fundraising and ratings must not appear on cards or in narration.

## All 35 races (national list)

`*` = featured state. Poll closing in ET: one time, or "main / last" where part of the state closes later.

| state | incumbent | nominees | other printed candidates | polls close (ET) | RCV |
|---|---|---|---|---|---|
| AL | Tommy Tuberville (REP), not on ballot | Barry Moore (REP); Everett Wess (DEM) | - | 20:00 | no |
| AK * | Dan Sullivan (REP), running | Dan Sullivan (REP, inc.); Mary Peltola (DEM) | Daniel J. Sullivan Jr., Gerald L. Heikes | 00:00 (Nov 4) / 01:00 (Nov 4) | yes |
| AR | Tom Cotton (REP), running | Tom Cotton (REP, inc.); Hallie Shoffner (DEM) | Jeff Wadlin | 20:30 | no |
| CO | John Hickenlooper (DEM), running | John Hickenlooper (DEM, inc.); Mark Baisley (REP); Bob Chew (OTH, Forward Party) | Christopher Baum, Blake Huber, Adam Withrow | 21:00 | no |
| DE | Chris Coons (DEM), running | Chris Coons (DEM, inc.); Michael Katz (REP) | - | 20:00 | no |
| FL (special, cl. 3) | Ashley Moody (REP), running | Ashley Moody (REP, inc.); Angie Nixon (DEM) | Neil Gillespie | 19:00 / 20:00 | no |
| GA | Jon Ossoff (DEM), running | Jon Ossoff (DEM, inc.); Mike Collins (REP) | - | 19:00 | no |
| ID | Jim Risch (REP), running | Jim Risch (REP, inc.); Todd Achilles (IND) | Matt Loesby, Natalie Fleming | 22:00 / 23:00 | no |
| IL | Dick Durbin (DEM), not on ballot | Juliana Stratton (DEM); Don Tracy (REP) | Whitfield Harrington Jr. | 20:00 | no |
| IA | Joni Ernst (REP), not on ballot | Ashley Hinson (REP); Josh Turek (DEM) | Thomas Laehn | 21:00 | no |
| KS * | Roger Marshall (REP), running | Roger Marshall (REP, inc.); Adam Hamilton (DEM) | David C. Graham | 20:00 / 21:00 | no |
| KY | Mitch McConnell (REP), not on ballot | Andy Barr (REP); Charles Booker (DEM) | Christopher Campbell | 18:00 / 19:00 | no |
| LA | Bill Cassidy (REP), not on ballot | Julia Letlow (REP); Jamie Davis (DEM) | - | 21:00 | no |
| ME * | Susan Collins (REP), running | Susan Collins (REP, inc.); Troy Jackson (DEM) | - | 20:00 | yes |
| MA | Ed Markey (DEM), running | Ed Markey (DEM, inc.); John Deaton (REP) | Shiva Ayyadurai, Joe Tache | 20:00 | no |
| MI * | Gary Peters (DEM), not on ballot | Abdul El-Sayed (DEM); Mike Rogers (REP) | Lydia Christensen, Tim Long, Douglas P. Marsh, Walter P. Kristy | 20:00 / 21:00 | no |
| MN | Tina Smith (DEM), not on ballot | Peggy Flanagan (DEM, Democratic-Farmer-Labor (DFL)); Michele Tafoya (REP) | Rebecca Whiting, Marisa Simonetti | 21:00 | no |
| MS | Cindy Hyde-Smith (REP), running | Cindy Hyde-Smith (REP, inc.); Scott Colom (DEM) | Ty Pinkins | 20:00 | no |
| MT | Steve Daines (REP), not on ballot | Kurt Alme (REP); Alani Bankhead (DEM); Seth Bodnar (IND) | Kyle Austin, Jami Dee Woodman | 22:00 | no |
| NE | Pete Ricketts (REP), running | Pete Ricketts (REP, inc.); Dan Osborn (IND, Independent (nominated by petition)) | Chuck Conboy, Mike Marvin, Robin Richards | 21:00 | no |
| NH | Jeanne Shaheen (DEM), not on ballot | Chris Pappas (DEM); John E. Sununu (REP) | Ed LaPlante | 20:00 | no |
| NJ | Cory Booker (DEM), running | Cory Booker (DEM, inc.); Justin Murphy (REP) | Veronica Fernandez, Joanne Kuniansky | 20:00 | no |
| NM | Ben Ray Luján (DEM), running | Ben Ray Luján (DEM, inc.); Larry Marker (REP) | - | 21:00 | no |
| NC | Thom Tillis (REP), not on ballot | Roy Cooper (DEM); Michael Whatley (REP) | Shannon Bray, Michael Dublin | 19:30 | no |
| OH (special, cl. 3) * | Jon Husted (REP), running | Jon Husted (REP, inc.); Sherrod Brown (DEM) | Greg Levy, William B. Redpath | 19:30 | no |
| OK | Alan Armstrong (REP), not on ballot | Kevin Hern (REP); N'Kiyla Jasmine Thomas (DEM) | Sevier White, Ron Meinhardt, Curtis Stinnett | 20:00 | no |
| OR | Jeff Merkley (DEM), running | Jeff Merkley (DEM, Democratic; also nominated by the Working Families Party, inc.); David Brock Smith (REP) | Gary Lyndon Dye, Chris Henry | 23:00 | no |
| RI | Jack Reed (DEM), running | Jack Reed (DEM, inc.); Raymond McKay (REP) | Michael Bahry | 20:00 | no |
| SC | Darline Graham (REP), running | Darline Graham (REP, inc.); Annie Andrews (DEM) | Mark Hackett, Kasie Whitener | 19:00 | no |
| SD | Mike Rounds (REP), running | Mike Rounds (REP, inc.); Brian Bengs (IND) | - | 20:00 / 21:00 | no |
| TN | Bill Hagerty (REP), running | Bill Hagerty (REP, inc.); Marquita Bradshaw (DEM) | Tharon Chandler, Andrew Gerena, Jeremy Hearn, Robert Jones, James Macon III, Yoshi Matthews, David Sutman Jr., Catherine Whitson | 20:00 | no |
| TX * | John Cornyn (REP), not on ballot | Ken Paxton (REP); James Talarico (DEM) | Ted Brown | 20:00 / 21:00 | no |
| VA | Mark Warner (DEM), running | Mark Warner (DEM, inc.); Bert Mizusawa (REP) | - | 19:00 | no |
| WV | Shelley Moore Capito (REP), running | Shelley Moore Capito (REP, inc.); Rachel Fetty Anderson (DEM) | S. Marshall Wilson | 19:30 | no |
| WY | Cynthia Lummis (REP), not on ballot | Harriet Hageman (REP); James W. Byrd (DEM) | - | 21:00 | no |

**Special rules and cross-endorsements**
- **Runoff rules:**
  - Georgia: majority required; runoff 2026-12-01 if needed.
  - Louisiana: plurality.
  - All other states: plurality, except the RCV states AK and ME.
- **Fusion and cross-endorsements:**
  - Oregon: Merkley is cross-nominated by the Working Families Party, and Chris Henry by the Progressive and Pacific Green parties.
  - Nebraska: Democratic Party support for Osborn, and no Democrat on the ballot.
  - Idaho and South Dakota: no Democrat on the ballot.
  - Montana: the state Democratic chair resigned on 2026-10-12 to endorse Bodnar (NBC Montana, cited by Wikipedia). That is an endorsement, so it is context only.
  - Alaska has no cross-endorsement in 2026: Peltola is a registered Democrat.

**Poll-closing sources**
- The Green Papers "2026 General Election Polling Hours", fetched 2026-11-02.
- For the featured states, also each fork's state source (see below).
- Unresolved:
  - New Hampshire: most towns close at 7 p.m. and cities at 8 p.m. The file uses 8 p.m. as both main and last.
  - Alaska's western Aleutians: some guides say 7 p.m. HAST (midnight ET); the file uses the conservative 1 a.m. ET.
  - Alabama: some Eastern-time polling places may close at 7 p.m. ET.

**Name and party details not fully settled**
- Florida's NPA candidate is spelled "Neil Gillespie" on Wikipedia and "Neil Joseph Gilespie" on The Green Papers. Unverified.
- Kentucky's Christopher Campbell is labelled "Kentucky" (party) by The Green Papers and Independent by Wikipedia. Coded OTH.
- Illinois' Whitfield Harrington Jr. is labelled "American Center" by The Green Papers and Independent by Wikipedia. Coded OTH.
- Montana's "Jami Dee Woodman (Nonpartisan)" appears only on The Green Papers, not on Wikipedia's list. Unverified; check the Montana SOS general list.
- Holdover senator names are written as senate.gov lists them, e.g. "Bernard Sanders" and "Angus S. King Jr.".

## Localisation conventions

- **Japanese (`name_ja`):** full katakana names as written by Kyodo, Nikkei, Jiji, AFPBB, CNN.co.jp, Asahi and Yomiuri.
  - NHK article bodies could not be read here (client-side rendering), so NHK's own renderings are unverified for every name.
  - Known splits:
    - Husted: ヒューステッド (Kyodo, Asahi) vs ハステッド (Yomiuri, Reuters). The file uses ヒューステッド.
    - El-Sayed: エルサイド (Kyodo; Nikkei from late October) vs エルサイード (earlier Nikkei, Reuters). The file uses エルサイド.
    - Murkowski: マカウスキ (AFPBB, Kyodo) vs マーカウスキー.
    - Moran: モラン (MOFA) vs モーラン (MOD).
- **Traditional Chinese (`name_zh`):** CNA (中央社) usage. CNA nearly always writes **surname only**, with the English name in parentheses (柯林斯、派克斯頓、塔拉里格、休斯泰德、塞德…), so `name_zh` is surname-only for consistency.
  - `name_zh_full` is filled only for Alaska, where the two Sullivans must be told apart. CNA itself writes 蘇利文 vs 小蘇利文; the initial-added full forms are constructed.
  - Other Taiwanese outlets sometimes differ, e.g. UDN 孔寧 for Cornyn, 漢密爾頓 for Hamilton, 薩依德 for El-Sayed. Stick to CNA forms.
- **Simplified Chinese (`name_zh_hans`):** mainland or Hong Kong media usage (Xinhua, China News Service, The Paper, HK01, ifeng, FT中文网, Tencent). These are usually full names and often a different transliteration from Taiwan's (帕克斯顿 vs 派克斯頓; 塔拉里科 vs 塔拉里格). They are not character conversions.
- **Spanish (`name_es`):** names unchanged, except that the Alaska Sullivans keep their middle initials.
- **Party names (`parties`):**
  - es: Partido Republicano / Partido Demócrata / Independiente, from the Texas SOS bilingual sample ballot.
  - ja: 共和党 / 民主党 / 無所属, from Nikkei.
  - zh: 共和黨 / 民主黨 / 無黨籍, from CNA.
  - zh_hans: 共和党 / 民主党 / 无党派, from Xinhua.
  - The Libertarian, Green and Other renderings in ja and zh are marked constructed.
- **Constructed renderings** are listed per person in `_constructed_fields`:
  - Ted Cruz zh_hans 克鲁兹
  - Jerry Moran zh / zh_hans 莫蘭 / 莫兰
  - Adam Hamilton zh_hans 汉密尔顿
  - Alaska: the initial-added ja forms of both Sullivans; all `name_zh_full` values except the senator Dan Sullivan's; Gerald Heikes zh / zh_hans.

## Open items before air

1. **Abdul El-Sayed's birth date and age.** Not confirmed by an allowed source; he is 41 or 42. Wikipedia says 1984-10-31. Do not show age in Michigan until it is verified for both candidates (`display_note`).
2. **Mike Rogers' birthplace.** Livingston County (campaign, Ballotpedia) vs Livonia (Wikipedia). The card uses the campaign's wording.
3. **Maine write-ins.** The newer list (SOS update of Oct 15-16) was not retrieved. Only the Aug 25 list of six was checked.
4. **Ohio ballot.** The SOS's own list was blocked; the Franklin County list was used. Confirm Greg Levy's printed label ("Other-party" vs "Nonparty").
5. **Kansas write-ins** were not checked. Precinct reporting on the KS, TX and OH state results sites is unverified (Cloudflare or 403), so `precincts` may need to be null.
6. **Alaska.** Confirm whether the Justice Department appeals the Nov 1 dismissal. It affects certification only.
7. **NHK renderings** for all names (see Localisation).
8. **Exact dates.** "In office since" dates for Collins (1997-01-07) and King (2013-01-03) are inferred from the opening day of each Congress, because Bioguide was blocked.

---

## Featured states: detailed notes

The per-state notes below were compiled from official sources, campaign sites, official bios and news (one researcher per state). They have been lightly edited for neutrality.

### Texas (TX) - Class 2, regular

#### Ballot (verified)
- Official source: Texas Secretary of State, Election Advisory 2026-22 (2026-08-28),
  https://www.sos.state.tx.us/elections/laws/advisory2026-22.shtml, and its attachments:
  - Sample ballot: https://content.govdelivery.com/attachments/TXSOS/2026/08/28/file_attachments/3762824/2026%20Sample%20Ballot-final.pdf
    U.S. Senator: Ken Paxton (Republican), James Talarico (Democratic), Ted Brown (Libertarian). Green and
    Independent columns are empty for U.S. Senator.
  - Declared write-in certification: https://content.govdelivery.com/attachments/TXSOS/2026/08/28/file_attachments/3762079/2026%20Write-In%20Ballot%20Certification-final.pdf
    U.S. Senator write-ins: Avery Ayers, Bradford "Brad" Hall, Zul Mohamed, Jade Simmons (read from the scanned
    PDF image; spelling as printed).
- Nomination results (major news):
  - Democratic primary 2026-03-03: Talarico defeated U.S. Rep. Jasmine Crockett.
    https://www.bloomberg.com/news/articles/2026-03-04/talarico-wins-texas-democratic-senate-primary-ddhq-projects ,
    https://www2.ljworld.com/news/national/2026/mar/04/talarico-wins-texas-senate-democratic-nomination/
  - Republican runoff 2026-05-26: Paxton defeated incumbent John Cornyn (AP projection).
    https://abc13.com/post/texas-attorney-general-ken-paxton-wins-gop-runoff-us-senate-ousting-longtime-sen-john-cornyn-ap-projects/19177494/ ,
    https://www.tpr.org/2026-05-26/ken-paxton-cruises-to-big-win-against-incumbent-sen-john-cornyn-in-texas-gop-primary-runoff
  - Libertarian: Ted Brown nominated at the state convention in Abilene, April 10-12, 2026 (Wikipedia, citing
    https://2026.lptexas.org/ ; ballot status itself confirmed by the SOS sample ballot).
- No late withdrawals, deaths, ballot changes or court rulings affecting the U.S. Senate ballot were found
  (searched news through 2026-11-01). Unrelated administration items reported in Oct 2026 (Tarrant County polling-place
  cuts; a DPS voter-registration backlog) do not change the ballot.

#### What changed this cycle
- Incumbent John Cornyn lost renomination (first Texas senator to lose renomination since 1970, per Wikipedia).
- Wesley Hunt (R) ran in the March primary and was eliminated; Colin Allred (D) withdrew in Dec 2025.

#### Card-inclusion decision
- Carded: Paxton (REP) and Talarico (DEM).
- Not carded (also_on_ballot): Ted Brown (LIB). FEC: about $14,257 raised as of 2026-10-14 (Wikipedia table citing FEC);
  named in only a few public polls at 3-7%. Below the meaningful-support bar. Write-ins not carded.

#### Candidate facts and sources
- Ken Paxton: birth 1962-12-23, Minot ND; B.A. psychology 1985 and M.B.A. 1986 Baylor; J.D. UVA 1991; Strasburger &
  Price and J.C. Penney counsel - NAAG profile https://www.naag.org/attorney-general/ken-paxton/ . Texas House
  District 70 (Jan 14 2003 - Jan 8 2013) and Texas Senate District 8 (Jan 8 2013 - Jan 13 2015), home city McKinney -
  Texas Legislative Reference Library https://lrl.texas.gov/legeLeaders/members/memberDisplay.cfm?memberID=5556 .
  Baylor student body president and 14 years running a law firm in McKinney - campaign https://kenpaxton.com/about .
  Age 63 also stated by CNA (2026-05-27) and AFP (2026-05-27). AG since 2015 (Fox 7 Austin, 2026-10-21; NAAG calls him
  the 51st AG). The Texas AG's own bio page (texasattorneygeneral.gov/about-office/meet-attorney-general) returned
  404/402 and was not used. NAAG's family details are out of date and were not used.
- James Talarico: Texas House bio https://house.texas.gov/members/3685/biography (born Round Rock; McNeil HS; degrees
  from UT Austin and Harvard; taught middle school on San Antonio's West Side; first elected 2018). LRL
  https://lrl.texas.gov/legeLeaders/members/memberDisplay.cfm?memberID=5831 : District 52 from 2018-11-19 (special
  election) to 2023-01-10, District 50 since 2023-01-10; home city Round Rock (D52) then Austin (D50).
  Master's in theological studies, Austin Presbyterian Theological Seminary, and "former public school teacher and
  nonprofit director": Texas Tribune via KUT (2025-09-05).
  Birth date 1989-05-17: Lex (Danish national encyclopedia, updated 2026-10-14) https://lex.dk/James_Talarico ; also
  cited by Wikipedia to Texas Monthly (Jan 2026, page returned 403 here). Age 37 consistent with CNA (2026-09-06,
  "37歲州眾議員塔拉里格") and Texas Tribune ("Talarico, 36", 2025-09-05).
- Uncertain / left general: degree subjects (Wikipedia says B.A. government 2011, M.Ed. education policy 2016) and the
  year of the seminary degree (Wikipedia says 2025; the Tribune's Sept 2025 wording "last year" implies 2024) could not
  be confirmed from an approved source, so the card lists degree levels without subjects/years.
- Military service: none listed in the NAAG profile (Paxton; it notes he is the son of an Air Force veteran) or in the
  Texas House bio (Talarico); both set to null.
- Positions come only from each campaign's issue pages (kenpaxton.com/issues; jamestalarico.com/issue/...), picked to
  cover comparable topics (border/immigration, taxes, health) plus one further issue each that the campaign
  emphasises (Paxton: gun rights and "defend the unborn", quoted; Talarico: banning super PACs/corporate PACs and
  congressional stock trading). The campaign pages' attack text about the opponent was not used.

#### Localised names
| person | ja | zh (Taiwan) | zh_hans |
|---|---|---|---|
| Ken Paxton | ケン・パクストン - AFPBB (AFP Japanese) https://www.afpbb.com/articles/-/3636895 ; Kyodo (via Kumanichi/Sakigake, 2026-10-01) uses パクストン | 派克斯頓 - CNA https://www.cna.com.tw/news/aopl/202605270097.aspx (UDN/World Journal headlines also 派克斯頓; a search snippet suggests Newtalk used 帕克斯頓, not opened) | 帕克斯顿 - HK01 (simplified) and ifeng |
| James Talarico | ジェームズ・タラリコ - AFPBB; Kyodo タラリコ; CNN.co.jp ジェームズ・タラリコ | 塔拉里格 - CNA (2026-03-04, 09-06, 10-19) | 塔拉里科 - HK01 |
| John Cornyn | ジョン・コーニン - AFPBB | 柯寧 - CNA (UDN/World Journal use 孔寧) | 科宁 - HK01, ifeng (NetEase self-media uses 康宁) |
| Ted Cruz | テッド・クルーズ - CNN.co.jp (2026-10) | 克魯茲 - CNA https://www.cna.com.tw/news/aopl/202411070025.aspx | 克鲁兹 - CONSTRUCTED (simplified conversion of CNA's form; no Xinhua/Zaobao page reachable) |

Notes: CNA uses surname-only renderings, so name_zh is surname only. Taiwanese (派克斯頓, 塔拉里格) and mainland/HK
(帕克斯顿, 塔拉里科) renderings differ for both nominees, so name_zh_hans is not a character conversion of name_zh.
Xinhua search and Zaobao search were blocked/404 from here; HK01's simplified edition and ifeng were used instead.
No NHK, Nikkei or Jiji page was reachable for these names; Kyodo (regional reprints), AFPBB and CNN.co.jp agree.
State name: テキサス州 (Kyodo), 德州 (CNA), 得州 (HK01).

#### Poll closing and results
- Polls 7 a.m.-7 p.m. local (SOS advisory page). Central Time closes 8:00 p.m. ET; El Paso and Hudspeth counties
  (Mountain Time) close 9:00 p.m. ET (270toWin; The Green Papers says "reportedly").
- Results: SOS election-night site https://results.texas-election.com/ (Angular app; data endpoints behind a
  Cloudflare challenge, so precinct/polling-location reporting could not be checked). 254 counties.
- No RCV; plurality winner (Texas Election Code Sec. 2.001).

### Alaska (AK) - U.S. Senate, class 2 (regular)

#### Ballot (verified 2026-11-02)
- Alaska Division of Elections certified general-election list (page last updated 2026-09-25):
  https://www.elections.alaska.gov/candidates/?election=26genr
  - Heikes, Gerald L. (Registered Republican), Palmer
  - Peltola, Mary (Registered Democrat)
  - Sullivan, Dan S. (Registered Republican) Incumbent
  - Sullivan, Daniel J. Jr. (Undeclared), Petersburg
  - Certified write-ins (not printed): Sidney "Sid" Hill (Undeclared), Heather McElwain (Registered Libertarian)
- General sample ballot, HD1 (checked text): "Heikes, Gerald L. (Registered Republican)", "Peltola, Mary (Registered Democrat)",
  "Sullivan, Daniel J. Jr." (no affiliation printed), "Sullivan, Dan S. (Registered Republican) Incumbent", Write-in; 5 ranking columns.
  https://www.elections.alaska.gov/election/2026/General/SampleBallots/HD1-JD1.pdf
- Primary (Aug 18) official summary: Peltola 82,244 (49.5%), Dan S. Sullivan 68,726 (41.4%), Daniel J. Sullivan Jr. 4,107 (2.5%),
  David Leslie (D) 1,850 (1.1%), Gerald L. Heikes 1,741 (1.1%), others below. https://www.elections.alaska.gov/enr26/results/ElectionSummaryReportRPT.pdf
  (figures taken from the Wikipedia transcription of that report; I did not open the PDF itself).
- Recent change: 4th-place David Leslie (D) withdrew on Mon Aug 31 (ADN: "the deadline to withdraw from the general election"),
  and 5th-place Gerald Heikes moved onto the general ballot. Leslie is not on the certified list or the sample ballot.
  https://www.adn.com/politics/2026/09/01/alaskas-4th-place-us-senate-finisher-drops-out-elevating-gop-candidate-to-ballot/

#### Two Dan Sullivans (facts only)
- Daniel J. Sullivan Jr. (Petersburg, retired elementary teacher, former U.S. Forest Service forestry technician, age 69) filed as a Republican.
  The Division ruled him ineligible (preliminary June 10, final ~June 15-16); Anchorage Superior Court reversed on June 26; the Alaska
  Supreme Court affirmed on/around June 29-July 2 (sources differ on the date: ADN URL is dated 2026/06/29, Wikipedia says July 2).
  The Division lists him "(Undeclared)" and prints no affiliation; the incumbent is printed with "Incumbent", which ADN reported the Division
  had not done for federal candidates in past sample ballots.
  https://www.adn.com/politics/2026/06/30/election-officials-sample-ballot-shows-how-they-seek-to-distinguish-two-dan-sullivans-in-us-senate-race/
  https://www.adn.com/politics/2026/06/29/alaska-supreme-court-rules-that-dan-j-sullivan-can-appear-on-the-ballot-against-sen-dan-sullivan/
- Keys: "sullivan" = incumbent Dan S. Sullivan; "sullivan_j" = Daniel J. Sullivan Jr. Every localised on-screen name of both carries the
  middle initial (ダン・S・サリバン / ダン・J・サリバン・ジュニア; 丹恩．S．蘇利文 / 丹恩．J．小蘇利文; 丹·S·沙利文 / 小丹·J·沙利文;
  es "Dan S. Sullivan" / "Daniel J. Sullivan Jr."). The plain media forms (ダン・サリバン, 丹恩．蘇利文, 丹·沙利文) are used only in the
  "senators" block. Recommend the page never shows a bare "Sullivan" in the AK results table.
- Legal items (for producers; not for cards): the U.S. Justice Department filed suit on Oct 22-23 seeking to block certification if the
  incumbent loses narrowly, citing possible voter confusion between the two Sullivans; U.S. District Judge Sharon Gleason dismissed it on
  Nov 1 (CNA 2026-11-02; Nikkei 2026-11-02 says the government may appeal; no appeal confirmed as of Nov 2). State and federal
  investigations into how the namesake candidacy came about were announced in late October; the people named deny involvement.
  None of this changes the ballot or election-night counting; it could only affect certification (target Nov 25).
  https://www.cna.com.tw/news/aopl/202611020005.aspx , https://www.nikkei.com/article/DGXZQOGM020960S6A101C2000000/

#### Card-inclusion decision
- Cards: Sullivan (incumbent, R) and Peltola (D). Daniel J. Sullivan Jr. (2.5% in primary) and Heikes (1.1%) are in also_on_ballot
  (with keys and localised names, because the live results table needs them). No public evidence of meaningful support was checked
  beyond primary results (no polls used, per rules).

#### Candidate facts: sources and verification
- Official Election Pamphlet candidate statements (State of Alaska; candidate-supplied, published by the Division) - primary source for
  age, birthplace, residency, education, positions held:
  - Peltola: https://elections.alaska.gov/doc/oep/2026/PELTOLA,MARY_US%20Sen_Eng_v1.pdf (age 53, born Alaska; communities Bethel 1973-79,
    Kwethluk, Tuntutuliak, Platinum, Bethel 1988-2025, Anchorage 2025-present; "Attended University of Northern Colorado, UAF, UAS, UAA";
    Alaska House 1999-2009, Bethel City Council 2011-2013, U.S. House 2022-2025; Exec. Director, Kuskokwim River Inter-Tribal Fish Commission;
    military: "Military mom - two sons have served in the U.S. Coast Guard")
  - Dan S. Sullivan: https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DAN%20S_US%20Sen_Eng_v2.pdf (age 61, born Fairview Park, OH;
    29 years in Alaska: Fairbanks 1997-98, Anchorage 1998-2002 and 2009-present; Harvard BA economics, Georgetown law/master's;
    Colonel, USMC; statement lists energy (NPR-A, ANWR), fisheries/bycatch/Russian and Chinese trawl-caught fish ban, tax cuts,
    military and Coast Guard buildup incl. $7B JBER recapitalization and four icebreakers, $1.4B healthcare, border/fentanyl)
  - Daniel J. Sullivan Jr.: https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DANIEL%20J.%20JR%20_US%20Sen_Eng_v1.pdf (age 69, born
    Evergreen Park, IL; Petersburg since May 1980; retired elementary school teacher)
  - Heikes submitted no statement; Alaska Beacon says he did not respond to its questionnaire.
- Official Senate bio (sworn in Jan 6, 2015; AG; DNR Commissioner; Asst. Secretary of State; NSC director; USMC 30 years, retired Feb 1, 2024
  as a colonel in the Marine Corps Reserve; Harvard BA 1987, Georgetown JD/MSFS 1993; married 1994, three daughters):
  https://www.sullivan.senate.gov/about/bio/
- Birth dates: Sullivan 1964-11-13 and Peltola 1973-08-31 come from the unitedstates/congress-legislators dataset (sourced from Bioguide);
  bioguide.congress.gov itself was behind a bot check and could not be opened. Ages match the state pamphlet (61, 53).
- Alaska Beacon voter guide (age on Election Day, birthplace/hometown, occupation): https://alaskabeacon.com/voter-guides/contests/2026-u-s-senate/
- Peltola "first Alaska Native sworn into Congress" (Sept 13, 2022): https://alaskapublic.org/news/2022-09-13/mary-peltola-makes-history-as-first-alaska-native-person-sworn-into-congress
- Positions:
  - Peltola: campaign priority pages (fisheries, energy, affordability, fixing-the-rigged-system) at https://marypeltola.com/priorities/
  - Sullivan: the campaign site has no issue pages (only "Meet Dan"); positions come from his official pamphlet statement and his
    official Senate press release of July 1, 2025 on H.R. 1 ("eliminates taxes on tips ... permanently boosts the per-child tax credit to $2,200";
    lease-sale mandates 1.6M acres ANWR, 20M acres NPR-A). The Senate site returned 403 to automated fetches; the release text was read via
    the LegiStorm mirror. His yes vote on H.R. 1 (Senate passage July 1, 2025) is confirmed by Alaska's News Source:
    https://www.alaskasnewssource.com/2025/07/02/facing-snap-medicaid-concerns-why-murkwoski-sullivan-say-they-voted-big-beautiful-bill/
    (senate.gov roll-call pages were blocked to automated fetches.)
  - Topic balance: both have energy, fisheries and taxes; the fourth item is each candidate's own emphasis (Sullivan: military/Coast Guard;
    Peltola: congressional term limits / stock-trading ban).
- Murkowski: appointed Dec 20, 2002 (history.house.gov and Congressional Directory, seen via search results; not opened directly);
  class 3, next election 2028.
- Prior-office dates for Sullivan (AG 2009-10, DNR 2010-13, State Dept 2006-09) are not given in the sources I could open, so the card lists
  the offices without dates.

#### Localised names
- Editor's note (final file): in races.json `name_zh` holds CNA's own forms (蘇利文 for the incumbent, 小蘇利文 for Daniel J. Sullivan Jr., 佩爾托拉, 穆考斯基; 海克斯 is constructed). The initial-added full forms in the table below are stored in `name_zh_full` and should be used on screen to tell the two Sullivans apart.
| person | ja | zh (Taiwan) | zh_hans | status |
|---|---|---|---|---|
| Dan S. Sullivan (senator block) | ダン・サリバン (Nikkei 2026-10-24, Jiji 2026-11-02, Kyodo 2026-10-29) | 丹恩．蘇利文 (CNA 2026-10-29; CNA also uses 蘇利文 alone) | 丹·沙利文 (Tencent News 2026-01-11) | found |
| Dan S. Sullivan (card) | ダン・S・サリバン | 丹恩．S．蘇利文 | 丹·S·沙利文 (ifeng 2026-10-31 writes 丹·S.·沙利文; punctuation normalised) | ja, zh constructed (initial added) |
| Daniel J. Sullivan Jr. | ダン・J・サリバン・ジュニア (Kyodo/Nikkei just call him "新人/無所属のダン・サリバン") | 丹恩．J．小蘇利文 (CNA: 小蘇利文; LTN: 丹恩．小蘇利文) | 小丹·J·沙利文 (ifeng 2026-10-31) | ja, zh constructed |
| Mary Peltola | メアリー・ペルトラ (Nikkei 2026-10-24; Reuters JP 2026-10-29) | 瑪麗．佩爾托拉 (CNA uses surname only, 佩爾托拉) | 玛丽·佩尔托拉 (Tencent 2026-01-11; ifeng 2026-10-31) | zh given name constructed |
| Gerald L. Heikes | ジェラルド・ハイクス (Reuters JP via Yahoo 2026-10-29) | 傑拉德．海克斯 | 杰拉德·海克斯 | zh, zh_hans constructed (no Chinese coverage found) |
| Lisa Murkowski | リサ・マカウスキ (AFPBB 2020; Kyodo, Jiji and Reuters JP also use マカウスキ per search results; マーカウスキー and マコウスキー (Japanese Embassy) also seen) | 莉莎．穆考斯基 (CNA uses surname only, 穆考斯基) | 丽莎·穆尔科斯基 (Tencent 2026-01-11) | zh given name constructed |
- State: アラスカ州 / 阿拉斯加州 / 阿拉斯加州.
- Japanese media mostly describe Daniel J. Sullivan Jr. as 無所属 (Nikkei photo caption "無所属候補のダン・サリバン氏"), matching party code IND.

#### RCV, poll closing, reporting
- RCV facts: https://www.elections.alaska.gov/election-information/ (tabulation "will begin after the last counting of ballots on the 15th day
  following election day ... in Juneau at the Director's Office"); calendar https://www.elections.alaska.gov/calendar/ (polls 7 a.m.-8 p.m.;
  results posted after 9 p.m.; domestic mail deadline Nov 13; overseas Nov 18; final regional count Nov 18; target certification Nov 25).
  15th day after Nov 3 = Wed Nov 18, 2026 (my date arithmetic; the Division gives the rule, not a dated RCV entry).
- Ballot Measure No. 2 (24ESEG), "An Act Restoring Political Party Primaries, Ending Ranked-Choice General Elections, and Repealing Recent
  Campaign Finance Laws", is on the Nov 3 ballot (sample ballot text). It does not change how the 2026 Senate race is counted.
- Poll closing in ET: midnight ET (AKST part) and 1 a.m. ET (Hawaii-Aleutian part) on Nov 4, from 8 p.m. local (Division calendar) and
  Green Papers time zones. Some media guides give 7 p.m. HAST for the western Aleutians (= midnight ET); unresolved, but 1 a.m. ET is the
  conservative last closing and matches 2026 poll-closing guides seen in search results.
- Reporting: by house district HD01-HD40 with precincts; district reports carry separate "District N - Absentee / Early Voting / Question"
  rows (checked on https://www.elections.alaska.gov/results/24PRIM/HD1.pdf). As of Nov 1 the Division reported 113,301 ballots received
  (early vote 58,262; by mail 24,332), useful for the votes-left scene. https://www.elections.alaska.gov/election-results/

#### Access notes
- elections.alaska.gov serves an incomplete TLS chain; I fetched it with full verification by adding the issuing GlobalSign intermediate
  (taken from the certificate's AIA URL and verified against the system roots). Ballotpedia, bioguide, senate.gov roll calls and the
  Wayback Machine blocked automated access. The shared web-search budget ran out near the end, so I could not run a final search for
  election-eve changes after the Nov 1-2 CNA/Nikkei/Jiji reports.

### Kansas (KS) - Class 2, regular

#### Ballot verification
- Kansas Secretary of State candidate list, "2026 General" (sos.ks.gov/elections/elections_upcoming_candidate.aspx, retrieved 2026-11-02 by posting the election drop-down; the table updates as filings are made). United States Senate rows:
  - Adam Hamilton, Democratic, ballot city Stilwell, filed 05/29/2026
  - Roger Marshall, Republican, ballot city St John, filed 01/22/2026
  - David C Graham, Libertarian, ballot city Overland Park, filed 05/12/2026
- The list does not show an independent Senate candidate. Declared write-in candidates are not on the ballot and were not checked.
- The primary was 2026-08-04; the State Board of Canvassers certified the results on 2026-09-01 (SOS press release, 09-01-26). Wikipedia primary figures: Marshall 79.9% vs Arch Naramore 20.1%; Hamilton 34.6% of an 11-candidate Democratic field (Christy Davis 14.2%, Noah Taylor 13.6%, ...). These figures come from Wikipedia and were not re-checked against the SOS official primary PDF.
- No withdrawals, replacements, deaths or court rulings affecting the Senate ballot were found. Marshall and Hamilton held debates on Sept. 12 (Kansas State Fair, WIBW/Kansas Radio Networks) and Oct. 21 (FOX4).
- A June 2026 Kansas Reflector story discussed what a 2025 vacancy-appointment law (SB 105) would do if Marshall resigned. That was hypothetical: Marshall did not resign and is on the ballot.

#### Card inclusion
- Cards: Marshall (REP, incumbent) and Hamilton (DEM). Graham (LIB) goes under also_on_ballot. Public polls that listed him showed about 3-4% (Emerson College/Nexstar 4%; RedBox Research 3%, as summarised on Wikipedia and in search results). He was not in either debate. The parent may revisit this if a stricter or looser threshold is used for other states.

#### Candidate facts and sources
- Marshall: birth date 1960-08-09 is from the unitedstates/congress-legislators dataset, which is built from the Bioguide (bioguide.congress.gov and congress.gov returned a Cloudflare 403 to our fetcher). The congress.gov API (DEMO_KEY) confirms birth year 1960. Born in El Dorado and grew up in Butler County (marshall.senate.gov/about; kansansformarshall.com/about). Education: Butler County Community College (attended); K-State B.S. biochemistry, class of 1982; KU School of Medicine M.D., class of 1987 (years from the campaign about page). Army Reserve 1984-1991, medical officer, captain (campaign about page; the Senate bio says "seven years in the Army Reserves"). U.S. House KS-1 2017-2021; sworn into the Senate 2021-01-03.
- Marshall's positions come from his campaign's issue pages ("The record"). Each bill was checked against the congress.gov API: S.1816 (119th) Improving Seniors' Timely Access to Care Act of 2025, sponsor Marshall; S.4418 Lowering Input Costs for American Farmers Act, sponsor Marshall, introduced 2026-04-28; S.42 Build the Wall Act of 2025, sponsor Barrasso, Marshall a cosponsor; S.593 Nationwide Consumer and Fuel Retailer Choice Act of 2025, sponsor Fischer, Marshall a cosponsor; S.5 Laken Riley Act, Public Law 119-1.
- Hamilton: birth date 1964-07-12. His own church newsletter "Weekly Update from Pastor Adam - July 12, 2024" (resurrection.church) says "60 years ago today" and "I'm excited to be 60". The Kansas Reflector (2026-04-30) gave his age as 61, which is consistent. He grew up in Prairie Village (campaign "Meet Adam" popup on hamiltonforkansas.com). His SOS ballot city is Stilwell. B.A. in pastoral ministry from Oral Roberts University, 1985 (oru.edu news, 2013-01-18). M.Div. from SMU's Perkins School of Theology (ORU article); class of '88 per SMU Magazine (blog.smu.edu/smumagazine/2010/05/14/perkins-honors-distinguished-alumnus-hamilton). Founding/senior pastor of the United Methodist Church of the Resurrection in Leawood, founded 1990. Per the Kansas Reflector, he keeps working for the church during the campaign but is likely not preaching. More than 30 books (adamhamilton.com/about; Kansas Reflector). Appointed in 2016 to the President's Advisory Council on Faith-Based and Neighborhood Partnerships (obamawhitehouse.archives.gov, 2016-01-29); it is listed under prior_offices as an appointed advisory role, and he has held no elected office. No military service appears in any bio, so military_service is null.
- Hamilton's positions come from hamiltonforkansas.com/issues. Our curl fetches get a 403 there, but WebFetch read the page and the quoted sentences were checked verbatim: "Requiring congressional approval before new tariffs take effect"; "Expand Medicare drug price negotiation and extend the savings to private insurance."; "Reverse the cuts to Medicaid and restore the ACA subsidies that hold premiums down."; "Prohibit members of Congress and their households from buying or selling individual stocks while in office."; "Finally pass the full farm bill after three years of Congressional delay."; "Cut prices at the pump with year-round E15."
- "Hometown" means where each candidate grew up (Marshall: El Dorado / Butler County; Hamilton: Prairie Village). The SOS ballot cities are St John (Marshall) and Stilwell (Hamilton). The St John entry was not looked into further.
- Excluded from the cards under the content rules: news coverage of disputes between the campaigns (ads, complaints, legal claims about the candidates' past work) and campaign-trail remarks. Hamilton's earlier party registration and his early exploration of an independent run (Wikipedia) were not verified against an allowed source and are not on the card.

#### Senators
- Marshall: Class 2, in office since 2021-01-03, seat up 2026, running.
- Jerry Moran (R): Class 3. First elected in 2010; term began 2011-01-03 and he was sworn in 2011-01-05 (congress-legislators dataset). Re-elected 2016 and 2022; current term expires 2029-01-03, so next election 2028 (senate.gov Class III page; moran.senate.gov/public/index.cfm/biography).

#### Localised names (found vs constructed)
- Marshall: ja ロジャー・マーシャル (CNN.co.jp, cnn.co.jp/usa/35254231.html; Jiji and Reuters/Newsweek Japan use マーシャル上院議員). zh 馬歇爾 (CNA, cna.com.tw/news/aopl/202610310007.aspx and 202610310003.aspx; PTS and UDN agree). zh_hans 马歇尔 (Xinhua, news.cn/world/20261101/...: "罗杰·马歇尔" then "马歇尔"). All found.
- Hamilton: ja アダム・ハミルトン (Nikkei DGXZQOGN2808K0Y6A021C2000000; Reuters via Newsweek Japan newsweekjapan.jp/articles/-/336849: アダム・ハミルトン牧師). zh 韓密爾頓 (CNA 202610310007, also UDN 9846293). Other Taiwanese outlets differ: UDN 9844706 uses 漢密爾頓, and Chinese Wikipedia uses 亞當·漢密爾頓. zh_hans 汉密尔顿 is CONSTRUCTED: no mainland or Singapore media rendering was found (Zaobao is not reachable; Xinhua's article does not name him). 汉密尔顿 is the standard mainland transcription of "Hamilton". If the stream's simplified text should mirror CNA instead, use 韩密尔顿.
- Moran: ja ジェリー・モラン (Japan MOFA press release pressit_000001_01306, title "モラン米国連邦上院議員…"; the page itself returned 403 and the rendering was confirmed through the search index). Japan's Defense Ministry writes ジェリー・モーラン (mod.go.jp/j/press/news/2024/10/23a.html). No NHK/Kyodo/Nikkei usage was found. zh 莫蘭 and zh_hans 莫兰 are CONSTRUCTED: no CNA or Taiwanese media usage was found. Chinese Wikipedia uses 傑里·莫蘭 / 杰里·莫兰, and CNA site search was rate-limited (429).
- Format: CNA gives surname-only Chinese forms with the English name in parentheses, so name_zh / name_zh_hans are surname-only. Full-name forms, if wanted (CONSTRUCTED except where noted): 羅傑．馬歇爾 / 罗杰·马歇尔 (Xinhua uses the latter); 亞當．韓密爾頓 / 亚当·汉密尔顿; 傑里．莫蘭 / 杰里·莫兰.
- State: カンザス州 (Jiji), 堪薩斯州 (CNA), 堪萨斯州 (Xinhua). Spanish names are unchanged.

#### Poll closing, RCV, results
- K.S.A. 25-106: Central-time counties default to 7:00-19:00 CST (other hours allowed, ending no later than 20:00 CST). Mountain-time counties default to 6:00-18:00 MST (may run to 19:00 MST). AP's "What to expect in Kansas on Election Day" (Oct. 30, 2026; syndicated at lanacion.com.ar) says polls close at 7 p.m. local: 8 p.m. ET for most of the state and 9 p.m. ET for the Mountain-time areas. KSN (2024) said all polls close at 7 p.m. and western Mountain-time counties report an hour later.
- Mountain-time counties per 49 CFR 71.7(d): Sherman, Wallace, Greeley, Hamilton (FIPS 20181, 20199, 20071, 20075). Hamilton County shares a name with candidate Hamilton, so focus by FIPS, not by name.
- No RCV. Plurality under K.S.A. 25-702, no runoff.
- Results are by county (105 counties, SOS). The SOS election-night page is https://ent.sos.ks.gov/kssos_ent.html (linked from the SOS elections page). It returned a Cloudflare JavaScript challenge, so its format and whether it shows precincts reporting are unverified. Mail ballots: the Legislature did not authorize a grace period for 2026 (SOS statement, June 29, 2026, after Watson v. RNC). In 2024 ballots postmarked by Election Day could arrive up to three days later; that no longer applies. Provisional ballots are counted at the county canvass. AP 2024 timing: first update 8:10 p.m. ET, halfway 9:48 p.m. ET, last 3:45 a.m. ET (~97%). More than 1 million votes were cast in the 2022 Senate race; get the exact 2022 baseline from the SOS 2022 official results.

#### Unverified / open
- Exact 2026 county hours: whether any Central-time county stays open until 8 p.m. CST (9 p.m. ET). The 2024 reporting said all polls close at 7 p.m. local. The last_et of 9 p.m. ET holds either way.
- Hamilton's M.Div. year (1988) rests on the SMU Magazine "'88" class tag, not a dated degree record.
- Final enactment status of the 2025 RCV-ban bill SB 6 (it does not affect this race).

### Maine (ME) - U.S. Senate, Class 2 (regular)

#### Ballot and nominees (verified)
- Printed ballot: **Collins, Susan M.** (Republican, Bangor) and **Jackson, Troy D.** (Democratic, Allagash). Nobody else is printed. Source: Maine Secretary of State (SOS), "2026 General Candidate List - FINAL.xlsx", linked from the SOS Upcoming Elections page (retrieved through the Wayback Machine captures of 2026-10-11 and 2026-10-30, because maine.gov returns HTTP 403 to automated fetches):
  - https://www.maine.gov/sos/elections-voting/upcoming-elections (capture: http://web.archive.org/web/20261030082156/https://www.maine.gov/sos/elections-voting/upcoming-elections)
  - https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20General%20Candidate%20List%20-%20FINAL.xlsx
  - Filing dates in that list: Collins 2026-02-25; Jackson 2026-07-27.
- Six **declared write-in** candidates for U.S. Senate (the SOS list dated 2026-08-25): Brent Andrews (Unaffiliated, York), Sigrid Ann Olson (Democrat, Cape Elizabeth), Gina Oswald (Independent, Strong), Joseph Steinberger (Faith in Humanity, Rockland), Michael Turcotte (Un-enrolled, Burnham), Ashley J. Webb (Democratic, Farmington).
  - https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/Nov26%20Declared%20Write%20in%20List.pdf (capture of 2026-09-07)
  - Also: Spectrum News Maine, 2026-08-26, https://spectrumlocalnews.com/me/maine/politics/2026/08/26/maine-s-u-s--senate-race-to-include-6-write-in-candidates--triggering-ranked-choice-voting ; The Green Papers, https://www.thegreenpapers.com/G26/ME (also shows 6 write-ins).
  - **Unverified:** the SOS page links a newer version of the write-in list ("Updated 10.15.26" / "10/16/26"). The archived copy of that version returned 403, so I could not check whether anyone was added or dropped after 2026-08-25. The October Green Papers page still lists all six.
- Graham Platner is **not on the ballot** and is **not** a declared write-in. Secretary of State Bellows said write-in votes for him count as blank, and the voter's next ranking can still count (Spectrum, 2026-08-26).

#### Recent change: Democratic replacement nominee (neutral facts only)
- June 9, 2026 primary: Platner won the Democratic nomination. Collins was renominated in the Republican primary.
- Platner announced on 2026-07-08 that he was leaving the race (Xinhua 2026-07-09, https://www.news.cn/world/20260709/b0432951020f42cc836d6b627aef56fa/c.html ; WABI/WMTW 2026-07-29). He formally filed his withdrawal on **2026-07-10** (SOS "2026 Post Primary Withdrawals & Replacement Candidates", updated 2026-09-22: https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20Post%20Primary%20Withdrawals%20%26%20Replacement%20Candidates%20-%20Updated%209.22.26_0.pdf).
  - Note: the national Wikipedia page dates the withdrawal 2026-07-08. That is the announcement date; the filing date is 07-10.
- Legal procedure (21-A MRSA sec. 374-A, https://legislature.maine.gov/statutes/21-A/title21-Asec374-A.html): a party committee may make a replacement nomination if the nominee withdraws by 5 p.m. on the 2nd Monday in July. The replacement deadline is 5 p.m. on the 4th Monday in July, which was 2026-07-27.
- The Maine Democratic Party chose a state convention to select the replacement, the first time a Maine party has replaced a nominee this way. The convention met at the Cross Insurance Center in Bangor on **2026-07-25**. Delegates voted on paper ballots and a simple majority was needed. Jackson beat Saundra Pelletier 566-5. Sources: WABI, https://www.wabi.tv/2026/07/25/maine-democrats-nominate-troy-jackson-us-senate-candidate/ ; KATV/TNND with AP, 2026-07-25, https://katv.com/news/nation-world/troy-jackson-replaces-graham-platner-as-maine-democrats-us-senate-nominee-politics-elections-voting-vote-polls-republican-sen-susan-collins-progressive-candidates-socialists-socialism-medicare-for-all-sexual-assault-allegation-accusation
- The SOS received the replacement nomination on **2026-07-27** (SOS withdrawals PDF).
- Eligibility objection, not a court case. On 2026-07-24, state Rep. James White (R) sent a letter to the SOS asking whether Jackson could be the nominee, because Jackson had run in the June 2026 Democratic primary for governor. White cited 21-A secs. 331, 351 and 363. The SOS listed Jackson as the replacement anyway, without a written determination (WABI/WMTW, 2026-07-29, https://www.wabi.tv/2026/07/29/republican-maine-lawmaker-questions-troy-jacksons-eligibility-be-democratic-nominee-us-senate/). I found no court filing or ruling, and Jackson appears on the FINAL candidate list. My web-search budget ran out before I could check again after early August, so treat "no court action" as "none found".

#### Card content: verification notes
- **Collins.** Born 1952-12-07 in Caribou. Graduated from St. Lawrence University in 1975. Worked on the staff of William Cohen. Commissioner of Professional and Financial Regulation (1987), SBA regional director (1992), Husson Center for Family Business (1994). Elected to the Senate in 1996 and re-elected in 2002, 2008, 2014 and 2020. Lives in Bangor. Sources: official bio https://www.collins.senate.gov/about/susan-collins ; campaign site https://susancollins.com/about/ , /faq/ , /track-record/.
  - Age 73 on 2026-11-03; Kyodo also gives (73).
  - End dates of her pre-Senate posts are not in the official bio, so only appointment years are given.
  - Other sources also list deputy treasurer of Massachusetts (1993) and the 1994 Republican nomination for governor. Neither is in her official bio, so both are omitted.
  - No military service is listed in her official bio (field null).
  - `in_office_since` 1997-01-07: her campaign FAQ says "served continuously since January 1997". The day is the opening day of the 105th Congress. I could not confirm the exact day on bioguide.congress.gov (Cloudflare block).
- **Jackson.** Born 1968-06-26. Associate degree from the University of Maine at Fort Kent (2000). Maine House 2002-2008; Maine Senate 2008-2014 and 2016-2024; Senate President 2018-2024. Lives in Allagash. Sources: campaign site https://www.jacksonformaine.com/troy-at-a-glance (updated 2026-10-27) and /about. Kyodo gives (58).
  - Birthplace: the campaign says "born and raised in Allagash"; Wikipedia gives Fort Kent. The card uses Allagash as hometown only, with no birthplace claim.
  - Wikipedia also lists Majority Leader (2013-2014) and Minority Leader (2016-2018). I could not confirm these against an allowed source (Ballotpedia is blocked by a bot challenge; the Maine Legislature's current pages no longer carry his bio), so they are omitted.
  - No military service is listed in his campaign bio (field null).
  - Wikipedia says he first ran for office as a Republican (2000) and was elected as an independent in 2002. This is not on his campaign site and was not verified; left off the card.
- **Positions.** All come from each candidate's own campaign site: Collins's Track Record and FAQ pages, and Jackson's Priorities page. Each candidate has 3 background items and 4 positions.
  - Collins's positions are mostly about her record, framed as "Says she authored...". Jackson's are policy proposals, framed as "Supports...".
  - Statements about the opponent were left out on both sides.
- **Senators.**
  - Collins: Class II, up in 2026 (https://www.senate.gov/senators/Class_II.htm).
  - King: Class I (https://www.senate.gov/senators/Class_I.htm), next election 2030. Independent, caucuses with Democrats (listed on https://www.democrats.senate.gov/about-senate-dems/our-caucus). Sworn in January 2013 (https://www.king.senate.gov/about). The day 2013-01-03 is the opening of the 113th Congress, inferred the same way as Collins's.
  - Senate composition (119th Congress): 53 Republicans, 45 Democrats, 2 others (https://www.senate.gov/about/parties-leadership/party-division.htm).

#### RCV and timing (verified against statute and the SOS)
- RCV applies in general elections only to federal offices; the SOS FAQ explains the 2017 Supreme Judicial Court advisory opinion behind this. Green Papers also cites a 2026-04-06 advisory opinion, OJ-26-1, to the same effect; I did not verify that one.
- Outright-win threshold under 21-A sec. 723-A(2), as amended by PL 2025 c. 363: a candidate wins outright with first-choice rankings on more than 50% of **all ballots cast for the office**. Ballots with a blank first choice, an overvote, or a first choice for an excluded candidate count in that total. So blank ballots and write-ins can force an RCV count even with only two printed names.
- Per the SOS FAQ, if no candidate clears that threshold, ballots and memory devices from every municipality are taken to a central site in Augusta for tabulation.
- Precedents:
  - 2024 ME-02: tally run 10 days after the election (FairVote, 2026-10-20).
  - June 2026 primaries: more than a week (Spectrum).
- Certification is due within 20 days (sec. 722).
- FairVote is an RCV advocacy group. Its piece is used only for the 2024 timing and the process description; the rules themselves are cited to statute and the SOS.

#### Poll closing and reporting
- Polls close at 8:00 p.m. ET statewide, and all of Maine is on Eastern time (21-A sec. 626).
- Towns with fewer than 100 residents may close their polls once every registered voter has voted. Expect a few early returns from tiny towns.
- Results come in by municipality. On election night, municipal clerks report first-choice results; the BDN gathers them and calls races with Decision Desk HQ (https://bangordailynews.com/elections-central/). The stream adds those up into 16 county totals.
- I did not verify how many reporting units there are (left null). One snippet seen in a search result said "487 towns, cities and territories" for the June 2026 RCV ballot transport, but I never opened the article.

#### Localised names (all found in media; none constructed)
| person | ja (source) | zh, Taiwan (source) | zh_hans (source) |
|---|---|---|---|
| Susan Collins | スーザン・コリンズ, Kyodo 2026-07-26 via Akita Sakigake https://www.sakigake.jp/news/article/20260726CO0047/ (also Kumamoto Nichinichi https://kumanichi.com/articles/2017879) | 柯林斯, CNA 2026-10-24 https://www.cna.com.tw/news/aopl/202610240046.aspx | 苏珊·柯林斯, Xinhua 2026-10-24 https://www.news.cn/world/20261024/df8148ce75724400aa0c63c0a7ab2ed9/c.html |
| Troy Jackson | トロイ・ジャクソン, same Kyodo article | 傑克森, same CNA article; also CNA via UDN 2026-10-19 https://udn.com/news/story/6813/9823149 | 特洛伊·杰克逊, The Paper (澎湃新闻) https://www.thepaper.cn/newsDetail_forward_33729768 |
| Angus King | アンガス・キング, CNN.co.jp https://www.cnn.co.jp/usa/35240264.html | 金恩, CNA 2025-11-10 https://www.cna.com.tw/news/aopl/202511100129.aspx | 安格斯·金, Xinhua 2025-11-11 http://www.news.cn/world/20251111/36ac3166b5e24687af31951ef6740211/c.html |

- Convention to harmonise across states. CNA writes the **surname only** plus the English name in parentheses, e.g. 柯林斯（Susan Collins）, so `name_zh` follows that. Xinhua and The Paper write the **full name**, so `name_zh_hans` is a full name. If the stream wants full names in Traditional Chinese, the forms would be 蘇珊·柯林斯 (zh.wikipedia), 特洛伊·傑克森 and 安格斯·金恩. The last two would be constructed: I did not confirm them on CNA.
- Hong Kong and some Chinese-language outlets write Jackson as 傑克遜 or 杰克逊 (Bastille Post, Mezha). CNA uses 傑克森.
- State name: メーン州 (Kyodo, Jiji and Asahi use メーン; some outlets use メイン州); 緬因州 (CNA); 缅因州 (Xinhua).
- For King's Japanese name, NHK, Kyodo and Nikkei pages could not be fetched (crawler blocks), so CNN.co.jp is used. The MOFA page (https://www.mofa.go.jp/mofaj/na/na1/us/page4_005013.html) returned 403.

#### Access limitations this session
- Blocked or unreachable: maine.gov (403; Wayback captures used instead), Ballotpedia (WAF challenge), bioguide.congress.gov (Cloudflare), Maine Morning Star and News From The States (403), and NHK, Asahi, Reuters, BBC and Zaobao (crawler blocks).
- The web-search budget ran out near the end, so late-October checks were not repeated: no new write-in changes or court actions after early August could be confirmed.

### Ohio (special election, class 3) - verification notes

Checked 2026-11-02 (UTC).

#### Ballot and nominees
- Ohio SOS pages (ohiosos.gov, liveresults.ohiosos.gov, publicfiles.ohiosos.gov) returned HTTP 403 to direct fetches from this host, so the SOS's own certified list could not be read here. The candidate list comes from the county certified list instead.
- **Franklin County Board of Elections, "2026 General Election Candidates", revised 2026-10-16**
  (https://vote.franklincountyohio.gov/getmedia/e0a4ca45-6893-45c1-8190-87696f8804b4/2026-General-Candidate-List-5).
  Under "U.S. SENATOR, Unexpired Term Ending 1-3-2029" it lists:
  - Sherrod Brown (Democratic)
  - Jon Husted (Republican)
  - Greg Levy (Other-party)
  - William B. Redpath (Libertarian)
  - Certified write-ins: Stephen Faris, Anthony Holliman, Timothy Telymonde

  The county's 46-day FWAB notice (Form 120) gives the same list:
  https://vote.franklincountyohio.gov/getmedia/352b644d-b348-447e-b60d-aa9b9193a297/2026-General-Form-No-120-FWAB-Notice-46-Day.
  Note: the source PDF contains other candidates' contact emails; none were copied.
- The 100-day FWAB notice (late July) listed only Brown, Redpath and Husted. Levy was added later. SOS directive 2026-24 dealt with verifying the signatures on the independent petition Levy filed on 2026-05-01 (https://www.ohiosos.gov/assets/dir2026-24-examination-verification-petitions-independent-candidate-us-senate.pdf). That directive was found by search only; the file itself could not be opened (403).
- **Greg Levy's label.** He filed as an independent by nominating petition. Ohio ballots do not print "Independent": independents choose "Nonparty candidate" or "Other-party candidate", and the county lists show "Other-party". ballot-access.org reported that the Party for Socialism and Liberation petitioned for him. In races.json he is coded IND with ballot_label "Other-Party Candidate". Confirm the exact ballot wording on a county sample ballot if it will appear on screen.
- **May 5, 2026 primaries** (SOS official canvass, cited via Wikipedia):
  - Husted was unopposed (736,413 votes).
  - Brown won 89.4% against Ron Kincaid.
  - Redpath was unopposed for the Libertarians.
  - Libertarian Jeffrey Kanter was disqualified in March 2026 over invalid petition signatures (cleveland.com, 2026-03-19).
- No withdrawals, deaths, court rulings or replacement nominees were found for this race.
- Brown's age: born 1952-11-09, so he is 73 on Election Day and turns 74 on Nov 9. Yomiuri (2026-10-30) also gives 73 for Brown and 59 for Husted.

#### Card inclusion
- Cards go to Husted (R, appointed incumbent) and Brown (D).
- Levy and Redpath are printed on the ballot but are below the serious-support bar:
  - Polls: 1-5% each in published polls compiled on Wikipedia.
  - FEC receipts through 2026-10-14: about $133k (Levy) and $55k (Redpath), against about $19.9M (Husted) and $68.4M (Brown).

  These figures were used only for the inclusion decision and are not shown on cards.

#### Bio sources and verification
- **Official biographies.** The primary source for dates, offices and degrees is the Congressional Directory (GPO), read through the govinfo API text:
  - CDIR-2026-02-20 for Husted and Moreno.
  - CDIR-2024-04-25 for Brown, whose entry still shows him as chair of Banking, Housing, and Urban Affairs.
- **Husted, education.** The Congressional Directory gives B.A. in education (1989) and M.A. in communications (1992), both from the University of Dayton. This agrees with a Dayton Daily News snippet. Wikipedia words the master's as "communication".
- **Husted, dates.** Appointed 2025-01-17 (Congressional Directory). Sworn in 2025-01-21 (unitedstates/congress-legislators dataset and Wikipedia). Born 1967-08-25 in Royal Oak, Michigan. Raised in Montpelier, Williams County. Lives in Columbus (Senate bio and Congressional Directory).
- **Husted, background facts** come from https://www.husted.senate.gov/about/: foster care and adoption, the 1989 Dayton Division III football title, and InnovateOhio and the workforce office.
- **Brown, residence.** He now lives in Columbus according to his campaign site. The Statehouse News Bureau (2025-03-24) reported that he and Connie Schultz moved from Cleveland to a Columbus suburb. The 2024 Congressional Directory still says "of Cleveland" because it predates the move.
- **Brown, Ohio House years.** The Congressional Directory gives 1975-82; Wikipedia gives 1975 to Jan 1983. The card uses 1975-1982.
- **Brown, Banking Committee chair, 2021-2025.** Sources are the 2024 Congressional Directory and banking.senate.gov press releases from 2021 (for example https://www.banking.senate.gov/newsroom/majority/chairman-brown-ranking-member-toomey-banking-subcommittee-assignments-117th-congress, found by search).
- **Military service:** neither candidate lists any in the Congressional Directory or the official and campaign bios, so the field is null.
- **Sites that could not be used:** Ballotpedia (WAF challenge), bioguide.congress.gov (Cloudflare 403), apnews.com (blocked) and ohiocapitaljournal.com (403).

#### Positions, all from the candidate's own site or record
- **Husted's campaign site** (jonhustedforsenate.com) has no issues page. Its bio page lists record items: Intel, TechCred, InnovateOhio, police funding. His positions therefore come from his Senate office site and his sponsored bills:
  - Upward Mobility Act page.
  - S.5271, photo voter ID. Per congress.gov, Husted is the sponsor; it was introduced 2026-08-05 and cloture on the motion to proceed failed 52-46.
  - S.5028, Ratepayer Protection Act, introduced 2026-07-16 with Husted as sponsor. What the bill does is described by Statehouse News Bureau (2026-10-29): it "would pressure state utility regulators to require data centers pay their own utility costs". Roll Call, Fox and Daily Signal report the companion House bill H.R. 9340 passed 417-3, and that the Senate version was blocked twice in September 2026. Coverage describes the bill as covering sites of 100 MW or more.
  - Border and fentanyl, from the Senate bio.
- **Brown's campaign site** (sherrodbrown.com) has no separate issues pages. All four positions come from the homepage text: trade deals, insulin and drug prices, corporate tax breaks, pensions and Social Security.
- The topics differ between the two candidates because each list follows what that candidate emphasizes. Both have 4 items and both have 3 background facts.

#### Left off the cards on purpose
- Disputes over campaign ads, news reports about outside groups' mailers and online videos, fact-checks, polling and fundraising. None of these should appear on cards.

#### Poll closing and results
- **Hours.** Polls are open 6:30 a.m. to 7:30 p.m. ET statewide under R.C. 3501.32, read on codes.ohio.gov. All of Ohio is in the Eastern time zone, so the main and last closing times are both 2026-11-03T19:30-05:00.
- **Mail ballots.** Franklin County's homepage says Ohio law now requires absentee ballots to be received by 7:30 p.m. on Election Day; the post-election receipt window is gone. Expect fewer late-arriving mail ballots than in 2022 and 2024. UOCAVA and provisional ballots are still handled in the canvass.
- **Results site.** The SOS results site is "Ohio Decides" (liveresults.ohiosos.gov), read via WebFetch. It provides:
  - Results by county.
  - An XML feed in NIST SP 1500-100 format, updated every 3 minutes on election night.
  - A "Ballots Cast" tab with outstanding UOCAVA and provisional ballots.

  The 2026 landing page does not mention precincts reporting. 2024 primary coverage in the Columbus Dispatch, carried on Yahoo and seen as a search snippet only, cited "31% of precincts reporting, according to the Ohio Secretary of State's website". Check the feed for precinct counts on the night.
- **Counties.** 88 counties.
- **Ranked-choice voting.** Ohio does not use it. NCSL lists Ohio Rev. Code 3505.011 (2026) as prohibiting RCV except where home-rule provisions may allow it. Kansas also appears on NCSL's list of states that prohibit RCV, which is relevant to the Kansas card.

#### Localised names (found / constructed)
None of these were constructed.

**Japanese**
- Husted. Japanese media use two renderings:
  - ヒューステッド: Kyodo (via Yahoo: https://news.yahoo.co.jp/articles/c07149822900367be5a5af7f74dc9c7a67c84c16 and .../3b6e1ad48e6c85738aacea11a8c8ad538f951062), Asahi (full name ジョン・ヒューステッド: https://www.asahi.com/articles/ASVBF1GX1VBFUHBI013M.html), Bloomberg/TBS, Jiji (Google News match on a 2026-10-18 Jiji article; the text was not opened) and CNN Japan.
  - ハステッド: Reuters Japan, Yomiuri (https://www.yomiuri.co.jp/world/20261028-GYT1T00062/), Newsweek Japan and JoongAng/Chosun Japanese.

  NHK's 2026-10-29 Ohio article (https://news.web.nhk/newsweb/na/nd-20261029de67800) could not be read beyond its lead: the body loads client-side and the API returned 403. NHK's rendering is therefore unverified. We use ジョン・ヒューステッド, which follows Kyodo and Asahi and is closest to the pronunciation "HEW-sted". ハステッド is the main alternative.
- Brown: シェロッド・ブラウン is used consistently by Reuters, Yomiuri, Asahi, Nikkei and Bloomberg.
- Moreno: バーニー・モレノ (Reuters Japan via Yahoo: https://news.yahoo.co.jp/articles/5a53f57d0efc6bded97553955514325088a18f73).

**Traditional Chinese (CNA)**
CNA writes surnames only, with the English name in parentheses on first reference. No Taiwanese mainstream source gave a full transliterated name, so name_zh is surname-only:
- Husted: 休斯泰德, https://www.cna.com.tw/news/aopl/202610190013.aspx and /202610230029.aspx. UDN/經濟日報, 中天 and 民視 use the same form.
- Brown: 布朗, same articles.
- Moreno: 莫雷諾, https://www.cna.com.tw/news/aopl/202604300012.aspx and /202607230007.aspx.

Other Chinese-language outlets render Husted as 赫斯特德 (World Journal, Epoch Times, Sing Tao, RFI), 胡斯特德 (Storm Media) or 赫斯特 (Bastille Post).

**Simplified Chinese**
- FT中文网 gives 乔恩•赫斯特德, 谢罗德•布朗 and 伯尼•莫雷诺 (https://www.ftchinese.com/interactive/298671 and /interactive/293925). The separator was normalised from • to ·.
- Mainland outlets appeared in Google News matches for 赫斯特德 (Xinhua 2026-07-09 "美国共和党砸钱保“红州”联邦参议员选举", ifeng, NYT中文网) and for 谢罗德·布朗 (QQ News). Those article texts could not be opened because Google's link decoder was rate-limited. Zaobao and Xinhua search were not reachable.
- Simplified usage for Husted is also mixed (赫斯特德 vs 胡斯特德 at ThePaper).

**Spanish**
Names are unchanged.

#### Recent changes to note on air
- Brown is running for the seat less than two years after losing the other Ohio seat to Moreno in 2024.
- Ohio's absentee-ballot receipt deadline is now 7:30 p.m. on Election Day.
- Levy qualified after the July 100-day notice, so the ballot has four printed names.

### Michigan (MI): regular Class 2 election, open seat (Gary Peters, D, not running)

#### Ballot verification
- I checked the official source: the Michigan Department of State "Official Candidate Listing, General Election Tuesday, November 3, 2026", report dated "721 Candidates as of Tue Oct 27 15:15:50 EDT"
  https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=GEN&electionYear=2026
  It lists six U.S. Senate candidates. None has a WITHD or DISQ flag.
  - Democratic Party: El-Sayed, Abdul (petitions, 04/14/2026)
  - Republican Party: Rogers, Mike (petitions, 04/17/2026)
  - Libertarian Party: Christensen, Lydia (convention, 06/29/2026)
  - U.S. Taxpayers Party: Long, Tim (convention, 07/20/2026)
  - Green Party: Marsh, Douglas P. (convention, 04/27/2026)
  - Natural Law Party: Kristy, Walter P. (convention, 08/31/2026)
  - No "No Party Affiliation" (independent) candidate qualified for U.S. Senate.
- The Green Papers also lists the same six, with no withdrawals and no declared write-ins for this race. The write-in filing deadline was 2026-10-23. https://www.thegreenpapers.com/G26/MI
- Ballotpedia's race page (Wayback snapshot 2026-10-14) lists the same six. Its Mike Rogers profile (snapshot 2026-10-23) names only five and leaves out Kristy, who filed late (08/31). I followed the official list.
- Primaries on 2026-08-04:
  - Democratic: El-Sayed beat U.S. Rep. Haley Stevens, about 48.5% to 47.5%. State Sen. Mallory McMorrow withdrew in July but stayed on the ballot (about 4%).
  - Republican: Rogers was unopposed. Bernadette Smith was disqualified for too few signatures (Wikipedia; not separately verified).
  - The two sources give slightly different primary vote totals: Wikipedia 744,952 / 731,160, Ballotpedia 740,950 / 726,057. This does not matter for the cards. Use the certified figures if the primary is ever shown.
- I found no reports of court rulings, deaths or ballot changes for this race.
- Recent news, as context only and not for the cards: on about 2026-11-01 several outlets reported that Rep. Haley Stevens said she would vote for Rogers (CNA, 2026-11-02: https://www.cna.com.tw/news/aopl/202611020011.aspx). This is an endorsement, so it stays out of the cards under the rules.

#### Senators
- Gary Peters (D):
  - Class 2. Serving since 2015. The term began 2015-01-03 and he was sworn in 2015-01-06, per the congress-legislators dataset.
  - Announced 2025-01-28 that he would not run again (AP via WTTW).
  - Listed as Class II on senate.gov.
- Elissa Slotkin (D):
  - Class 1. In office since 2025-01-03; next election 2030.
  - Listed as Class I on senate.gov.
- Sources: https://www.senate.gov/senators/Class_II.htm, https://www.senate.gov/senators/Class_I.htm, https://www.peters.senate.gov/about, https://www.slotkin.senate.gov/about/, https://unitedstates.github.io/congress-legislators/legislators-current.json

#### Card-inclusion decision
- The cards cover El-Sayed (DEM) and Rogers (REP).
- The four minor-party nominees go in also_on_ballot. They polled 1-3% where named (e.g. the Mitchell Research full-field poll of 2026-10-01 listed on Ballotpedia) and I found no serious fundraising. Polls were used only for this decision; they appear nowhere in the cards.

#### Candidate facts: sources and caveats
Abdul El-Sayed (DEM):
- Birth date is NOT verified (left as birth_date null, age null).
  - Wikipedia gives 1984-10-31, born in Rochester Hills. Its cited source (Vogue, 2018) does not state the date.
  - Allowed sources only bracket the date: Vogue 2018-08-01 says "33-year-old" and Fox 2 Detroit 2026-10-21 says age 41. Together these put his birth between 1984-10-22 and 1985-08-01.
  - So he is 41 or 42 on election day; the Wikipedia date would make him 42. birth_year 1984 comes from Wikipedia only.
  - If a card needs an age, confirm it first. Do not display a guess.
- Hometown: the campaign says he was "raised in Southeast Michigan". Ballotpedia lists Andover High School (2003). He lives in Ann Arbor (campaign "Meet Abdul" page). I left residence off the card so both candidates get the same hometown format.
- Education:
  - Ballotpedia (Wayback 2026-07-20): B.S. University of Michigan 2007, D.Phil. Oxford 2011, M.D. Columbia 2014.
  - Campaign: Rhodes Scholar, NIH-funded fellowship.
- Offices:
  - Detroit Health Department executive director and health officer, 2015 to Feb 2017 (Ballotpedia).
  - Wayne County Dept. of Health, Human and Veterans Services director: the role is confirmed by Fox 2. The years 2023-2025 come from Wikipedia (named Dec 2022, started March 2023, resigned April 2025 to run).
- No military service appears in the campaign biography or on Ballotpedia, so military_service is null.
- Positions come from campaign priority pages (accessed 2026-11-02):
  - Medicare for All: /priority/medicare-for-all-the-path-to-a-healthier-america/
  - Corporate housing ownership, wealth tax and the over-$1M rate: /priority/money-in-your-pocket/
  - Citizens United and outside spending: /priority/money-out-of-politics/
  - These match his three stated top priorities.

Mike Rogers (REP):
- Birth date 1963-06-02, from the congress-legislators dataset, which is derived from Bioguide R000572. Bioguide itself was blocked by Cloudflare from here. Fox 2 and Bridge give age 63 in Oct 2026, which is consistent. Age on 2026-11-03 is 63.
- Hometown: the conflict is noted, not resolved.
  - Campaign (Meet Mike): "born and raised in Livingston County", graduated from Howell High School.
  - Ballotpedia: "born in 1963 in Livingston County".
  - Wikipedia: born in Livonia (Wayne County), family moved to Brighton Township.
  - The card says "Livingston County, Michigan (Howell High School)", attributed to the campaign.
- Military: U.S. Army 1985-1989 (Ballotpedia; Wikipedia says first lieutenant, 7th Infantry Division). The campaign says "Lieutenant in the United States Army".
- FBI special agent, 1989-1994 (Ballotpedia), in Chicago on organized crime and public corruption cases (campaign).
- Offices:
  - Michigan Senate, 26th District, 1995-2000 (Ballotpedia; Wikipedia gives 1995-01-01 to 2001-01-03).
  - U.S. House, MI-8, 2001-2015.
  - House Intelligence Committee chair, 2011-2015 (Wikipedia; AP: "during his last two terms").
- After Congress: business owner in cybersecurity (Ballotpedia; campaign).
- Positions come from the campaign site (accessed 2026-11-02):
  - /healthplan: price-posting fines, insurer denial penalties. The plan also proposes expanding "Trump Rx", which is not on the card.
  - /housingplan: 529 down payments, tax-free construction zones.
  - Homepage: "bringing manufacturing jobs back home ... protecting seniors' social security & medicare".
  - The site has no general issues page beyond these.
- Positions were chosen to be parallel: housing and health care for both, then two of each candidate's own headline priorities.
- Not used: anything on the campaigns' opposition pages (e.g. rogersforsenate.com/what-michiganders-need-to-know is entirely about the opponent).

#### Localised names
- I verified all renderings in media. None is constructed.

Japanese (ja):
- El-Sayed: アブドゥル・エルサイド
  - Kyodo via 熊本日日 2026-08-05: https://kumanichi.com/articles/2022393 (also 秋田魁 https://www.sakigake.jp/news/article/20260805CO0167/)
  - Kyodo rally story: https://kumanichi.com/articles/2050539
  - Nikkei used エルサイド from late Oct 2026, e.g. 2026-10-31 https://www.nikkei.com/article/DGXZQOGN293HS0Z21C26A0000000/
  - VARIANT アブドゥル・エルサイード: Nikkei in Aug to early Oct 2026 (https://www.nikkei.com/article/DGXZQOGN05BBS0V00C26A8000000/), Reuters Japan / Newsweek Japan (https://www.newsweekjapan.jp/articles/-/330480), JETRO and Toyo Keizai.
- Rogers: マイク・ロジャース
  - Kyodo "ロジャース元下院議員": https://kumanichi.com/articles/2050539
  - Nikkei keyword tag "マイク・ロジャース"
  - Reuters Japan: https://www.newsweekjapan.jp/articles/-/330480
  - VARIANT ロジャーズ: JETRO 2026-08-06 and ANN regional pages.
- Peters: ゲイリー・ピーターズ
  - Nikkei 2025-04-30 keyword: https://www.nikkei.com/article/DGXZQOGN3001Q0Q5A430C2000000/
- Slotkin: エリッサ・スロットキン
  - Nikkei articles of 2025-10-26 and 2026-08-04, seen in Nikkei search results: https://www.nikkei.com/search?keyword=%E3%82%B9%E3%83%AD%E3%83%83%E3%83%88%E3%82%AD%E3%83%B3
  - VARIANT スロトキン appears on minor sites.
- NHK: I could not check. NHK ONE article bodies are not in the served HTML; the API returns only headline and abstract. NHK covered the race (e.g. https://news.web.nhk/newsweb/na/nd-20261026de65474), but I could not read the names it used.

Traditional Chinese (zh), Taiwan CNA:
- CNA uses the surname only, with the English name in parentheses on first mention.
- El-Sayed: 塞德. CNA 2026-08-06 https://www.cna.com.tw/news/aopl/202608060005.aspx and 2026-11-02 https://www.cna.com.tw/news/aopl/202611020011.aspx. Other Taiwanese and US-Chinese media (UDN/World Journal) use 薩依德; Fount Media uses 阿卜杜勒·埃爾-薩伊德.
- Rogers: 羅傑斯 (same CNA articles). Other Taiwanese outlets write 麥克·羅傑斯.
- Peters: 皮特斯. CNA 2026-07-22 https://www.cna.com.tw/news/aopl/202607220102.aspx and 2025-08-22 aipl/202508220011. Other outlets use 彼得斯.
- Slotkin: 絲拉金. CNA 2026-04-30 https://www.cna.com.tw/news/aopl/202604300012.aspx. Other Taiwanese outlets use 斯洛特金.
- Michigan: 密西根州 (CNA).
- If the zh stream wants full names on screen, CNA gives none, so a full form would have to come from other Taiwanese outlets or be constructed. Decide one form and use it throughout.

Simplified Chinese (zh_hans), mainland media:
- El-Sayed 阿卜杜勒·赛义德, Rogers 迈克·罗杰斯, Peters 加里·彼得斯
  - Xinhua 2026-08-12: https://www.news.cn/world/20260812/ec4b6a25d78c4c61bbb47d61a3255aa6/c.html
  - Xinhua 2026-08-23: https://www.news.cn/world/20260823/4e57704eac764d729d0b8246170e9a93/c.html
- Slotkin 埃莉萨·斯洛特金
  - China News Service 2026-06-25: https://www.chinanews.com.cn/cj/2026/06-25/10647068.shtml
- Michigan: 密歇根州 (Xinhua).

Spanish (es):
- Names are unchanged.
- State name "Míchigan" is the Spanish Wikipedia title (RAE spelling). US Spanish-language outlets may write "Michigan" without the accent; I did not verify this.

#### Poll closing, RCV, reporting
- Polls are open 7 a.m. to 8 p.m. local time.
  - The four Central-time Upper Peninsula counties (Dickinson, Gogebic, Iron, Menominee) close at 9 p.m. ET.
  - Everywhere else closes at 8 p.m. ET.
  - Source: Votebeat, 2026-08-04 (primary-cycle explainer). The same law applies on 11-03, and the Liberty Twp (Wexford) clerk page confirms 7 a.m.-8 p.m. for 2026-11-03.
- RCV: Michigan uses plurality voting.
  - State law currently prevents RCV (Bridge Michigan).
  - Wikipedia's 2026 Michigan elections page lists only Proposals 1 and 2 on the ballot, neither about RCV. I did not cross-check this with the Board of State Canvassers.
- Reporting:
  - About 1,600 local clerks report to county clerks. County websites post unofficial results through the night.
  - The state page receives a county only once all of that county's precincts are in (Votebeat).
  - The SOS's 2026-08-04 release expected full unofficial results about 24 hours after polls closed, with statewide results at mi.gov/vote.
  - The state results site used in past cycles (mielections.us) timed out from here, so its 2026 URL is not verified.

#### Uncertain / not verified
- El-Sayed's exact birth date and age on election day.
- Rogers's birthplace (Livonia or Livingston County).
- NHK's renderings.
- The 2026 URL for state-level results.
- Absence of an RCV proposal: this rests on Wikipedia only.
- I stopped further lookups because the shared web-search budget ran out mid-task. Remaining checks were limited to direct fetches of known pages.

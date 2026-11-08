# Legal and platform rules: US 2026 midterm results streams (es / ja / zh)

Researched 2026-11-02 (election day Tue 2026-11-03). Scope: an AI-narrated, student-run YouTube results stream
(see `docs/ELECTION.md`). This is research, not legal advice. Where the law is unsettled, the rule given is the
conservative one. "Not found" means I searched and found nothing; it does not prove that nothing exists.

---

## Rules for the build

Prompt rules and QC checks. Each one points to the section that backs it.

**Race calls and data (s1, s4)**
1. Never call, project or imply a winner ourselves. Use only the official count, with "leads / ahead / trails / behind by N votes".
2. Name a winner only as an AP declaration taken from a published news report. AP *declares* winners and says it does not project, so change "AP projects" in ELECTION.md to "AP has declared".
3. Approved call wording. EN "The Associated Press has declared X the winner"; ES "La agencia AP declaró ganador(a) a X"; JA "AP通信は、X氏の勝利（当選確実）を伝えました"; ZH "美聯社宣布X勝選 / 美联社宣布X胜选".
4. Every sentence that contains a call names AP. The screen shows "Race call: The Associated Press (via <outlet>), <time> ET" in text, never the AP logo.
5. Use one call source only, AP. Never relay DDHQ or network decision-desk calls, and never make our own.
6. Take AP calls only from public news reports (apnews.com stories or other outlets). Never scrape or use AP's licensed results feed or API, AP graphics, or AP article text, and restate each call in our own words.
7. If AP retracts a call, or a report is ambiguous, remove the call at once and say so on air. Never re-infer a call.
8. Vote counts come only from the state's official site. Never substitute AP, network or newspaper tallies; if the state has not published, say "no official count published yet".
9. Label every count "Unofficial results · <state office> · as of <source time> ET"; results are final only when certified.
10. Take only the numbers from state sites. No screenshots, page layouts, state seals, agency logos or framing of their pages, and no wording that implies the state endorses us.
11. Respect access controls. Never bypass bot checks, captchas or rate limits; poll at 60 s or slower with an honest client (Ohio's live site served a bot check, see s1b).
12. No exit polls and no AP VoteCast figures or characterisations, even when quoted in news. No AP "expected vote" or "% of expected vote in" figures, and no turnout models.
13. Say "votes left" only as a comparison: "votes counted so far equal X% of the 2022 midterm total". Never "X% of the vote is in" or "N votes remain".

**Look, photos, names (s1d, s1e, s6)**
14. Candidate photos must be federal official portraits (senate.gov, house.gov, GPO via unitedstates/images) or free-licensed images shown with their credit. Otherwise use no photo.
15. Photo parity: every candidate in a race gets the same photo treatment, same size and crop, or none get photos.
16. Never use network or brand names, segment names, logos or banner styles (list in s1e). Use our own channel name, fonts and palette; generic maps, bars and balance-of-power graphics are fine.
17. Never play network or AP video or audio, not even a clip of a call (copyright, and Content ID scans live streams).
18. No "Official" and no network-like naming in the channel, title or stream name (YouTube impersonation policy).

**Election and campaign law (s2)**
19. No express advocacy in any language: no "vote for / against", "support", "defeat", "we hope X wins", and no get-out-the-vote calls tied to a candidate.
20. No contact or coordination with any campaign, party or PAC. Accept none of their content, money, sponsorship or requests, and air no ads or campaign videos.
21. No donation or fundraising links for anyone, and never frame Super Chat or memberships as support for a candidate.
22. Make no voting-procedure statements (deadlines, eligibility, locations). The only exception is official poll-closing times, attributed to the state.

**AI disclosure (s3, s6)**
23. Keep a disclosure on screen at all times, in the stream's language: the script is AI-written, the voice is synthetic, the results are unofficial, and the stream is not affiliated with any media outlet, campaign or government (strings in s6b).
24. Before going live, set `status.containsSyntheticMedia=true` on the broadcast's video id with `videos.update` (`liveBroadcasts` has no such field). Expect YouTube's more prominent player label.
25. Never synthesise a real person's voice or likeness (candidates, senators, anchors). Show quotes as on-screen text with their source, introduced as "According to her campaign website, ...".
26. No AI-generated images of candidates, voters, polling places or events.

**Timing (s4)**
27. Show no numbers, leads or characterisation for a state until its last polls close. Times are ET: OH 7:30 pm, ME 8:00 pm, TX 9:00 pm, KS 9:00 pm, MI 9:00 pm, and AK 1:00 am Wednesday.
28. Before that time a state scene is preview-only: senators, candidates, history and a countdown. The national map shows only the states "Polls open", "Polls closed", "Counting" and "AP declared".
29. Never say a state's polls "have closed" before its last close. Say instead "Most polls have closed; polls in El Paso and Hudspeth counties close at 9 pm ET".

**Accuracy and defamation (s5)**
30. Take candidate facts only from the candidate card (official bio, government records, ballot, the candidate's own site), each with its source. The writer may not add facts.
31. Attribute positions every time: "X says ...", "On his campaign website, X says ...". Describe votes as "voted for / against <bill> in <year>", with the congress.gov record as source.
32. No allegations, investigations, lawsuits, scandals, health, family, polls, endorsements or opponents' attacks.
33. No predictions, odds, "path to victory", "needs X% of the remaining vote", "expected to win" or "favoured".
34. Correct an error on air in the next pass of the scene and note it in the description.

**Ranked choice (s5b)**
35. Maine: say "first-choice votes". An outright win needs a first-choice ranking on more than 50% of ALL Senate ballots cast, including blank ballots. Never compute or predict the ranked-choice result; if it is needed, the Secretary of State runs it in Augusta, likely into the following week.
36. Alaska: say "first-choice votes". The ranked-choice tabulation is on Nov 18 and certification is targeted for Nov 25, and absentee ballots are still arriving. Ballot Measure 2 (repeal) does not change this count. Party labels are the candidate's registration as printed on the ballot.

**Neutrality (s7)**
37. Results verbs only: leads, ahead, trails, behind. Give margins in votes and in percentage points.
38. Apply the banned-word lists in s7 in all four languages as a QC regex, plus a second LLM check for loaded framing.
39. Party names: "Republican Party / Republican" and "Democratic Party / Democrat". The adjective is "Democratic", never "Democrat Party". Use independents' and third parties' labels exactly as the ballot prints them.
40. Give every candidate the same fields. Sentence counts within ±1 for every ballot-listed candidate (up to 4; above that, the two leading in the official count get equal time and the rest one line each). Alternate who is named first.
41. Describe counties only with numbers ("voted 61% for Trump in 2024"), never "stronghold", "bastion" or "deep red".
42. Colours: red = Republican, blue = Democratic, shown in a legend in every language. Never use Taiwanese camp terms (藍營 / 綠營) for US parties.

**YouTube metadata and channel (s6)**
43. Titles and thumbnails must be true and current. No winner, check mark or "projected" until AP declares, no network names, equal-size faces or none. Countdowns to the real poll-closing times are fine.
44. No claims of fraud, rigging or a "stolen" election, and no false claims about eligibility or death. Do not relay anyone's fraud allegations; that is outside the stream's scope.
45. The content must change with the data. No identical loops for hours (YouTube's inauthentic-content monetisation policy).
46. The description carries the source list, the AI disclosure, "unofficial results", "not affiliated" and a corrections note. A strike on this stream hits the whole channel, including the weather desks.

---

## 1. Copyright, hot news, data, photos, look

### 1a. Relaying AP race calls (and why not DDHQ or networks)

**The law**
- **Facts are not copyrightable.** *Feist Publications v. Rural Telephone*, 499 U.S. 340 (1991) holds this; 17 U.S.C. 102(b) excludes facts, ideas and discoveries; a compilation is protected only "thinly", for its selection and arrangement. "AP has declared X the winner" is a fact about the news. AP's sentences, graphics and data tables are protected expression.
- **The original hot-news case.** *International News Service v. Associated Press*, 248 U.S. 215 (1918): the news element is not copyrightable. INS still committed unfair competition by taking AP bulletins and selling them to competing papers *as its own* (quasi-property between competitors). After *Erie* (1938) the doctrine survives only as state law, chiefly New York's.
- **Narrowed to almost nothing.** *NBA v. Motorola*, 105 F.3d 841 (2d Cir. 1997): sending real-time game scores to pagers was not copyright infringement, and the hot-news claim was preempted. The claim survives only if all of these hold:
  - the plaintiff gathers the information at cost;
  - the information is time-sensitive;
  - the defendant free-rides on it;
  - the defendant competes directly with the plaintiff's product;
  - free-riding would threaten the product's existence.
- **Attributed reporting is not misappropriation.** *Barclays Capital v. Theflyonthewall.com*, 650 F.3d 876 (2d Cir. 2011): a service that quickly reported, *with attribution*, banks' stock recommendations was reporting news. The hot-news claim was preempted. In substance the court said the firms *make* the news, and that doing so does not give them control over who *breaks* it.
- **The caution.** *AP v. All Headline News*, 608 F. Supp. 2d 454 (S.D.N.Y. 2009), decided before *Barclays*: a hot-news claim survived dismissal where the defendant rewrote and resold AP stories as a competing wire. Systematically repackaging AP *content* is the risky pattern.
- **Trademark.** Naming "The Associated Press" in plain text to attribute a call is nominative fair use (*New Kids on the Block v. News America Publishing*, 971 F.2d 302 (9th Cir. 1992)). AP's logo is not needed and is not used.

**AP's own framing**
- AP says its race calls "are not predictions"; they are declarations based on analysis of vote results ([AP explainer, Mar 2026](https://www.clickondetroit.com/news/politics/2026/03/03/its-election-season-again-this-is-why-and-how-ap-calls-races-across-the-country/)).
- "The AP doesn't 'project' winners as many TV networks do" ([WUSF/NPR, 2024](https://www.wusf.org/2024-11-05/race-calls-101-how-the-ap-declares-winners)).
- AP does not call a race before the last polls close in that jurisdiction ([HPR/AP explainer](https://www.hawaiipublicradio.org/national-international/2022-11-08/explainer-how-can-the-associated-press-call-races-right-as-polls-close)).
- So the correct verb is "declared" or "called", not "projects" (Rules 2-3).

**Practical rule**
- Relaying individual Senate race calls with attribution, after they appear in public reports, is squarely within *Barclays*. We report a newsworthy fact, credit AP, sell no competing feed, and copy no AP expression.
- Risk rises if we scrape AP's licensed results or API, copy AP text or graphics, or run a real-time all-races call feed.
- Use AP only. DDHQ and the network decision desks apply different standards, and mixing sources invites contradictory "winners" on screen. DDHQ and the networks are also commercial data sellers; the same *Barclays* analysis applies, but there is no need to use them.

### 1b. Official vote counts from state results sites

- Vote counts are facts (*Feist*) and public records under each state's records law, such as Ohio R.C. 149.43 and Michigan FOIA, MCL 15.231 et seq. No state can own the numbers.
- What a state can own: page design, text, graphics, seals and logos. Portal terms of use are browsewrap contracts with weak enforceability, but they are cheap to respect. Take the numbers, credit the office, and render our own graphics.
- **Access.** The federal anti-hacking law (CFAA) does not reach public pages (*Van Buren v. United States*, 593 U.S. 374 (2021); *hiQ Labs v. LinkedIn*, 31 F.4th 1180 (9th Cir. 2022)). Deliberately defeating a technical barrier is where risk starts.

| State | Results publisher | Reuse terms found (site- or portal-level) | Rule |
|---|---|---|---|
| TX | Texas Secretary of State election-night results (Civix-hosted) | No SOS copyright page found. The statewide [State Website Linking and Privacy Policy](https://prod.dir.texas.gov/sites/default/files/2021-02/State%20Website%20Linking%20and%20Privacy%20Policy.pdf) says publicly accessible state-site information may be copied (subject to agency limits, not misleadingly). The SOS [link policy](https://www.sos.texas.gov/linkpolicy.shtml) needs no permission | Numbers + credit "Texas Secretary of State" |
| AK | Division of Elections (elections.alaska.gov) | No Division reuse terms found. Other Alaska agencies reserve rights in site content ([Dept. of Law terms](https://law.alaska.gov/terms.html), [DOA copyright notice](https://doa.alaska.gov/dof/help/copyright.html)); that covers text and graphics, not counts | Numbers only, no graphics |
| KS | Kansas Secretary of State election results | No SOS terms found. The Kansas.gov portal (INK) has [terms of use](https://portal.kansas.gov/portal-policies/terms-of-use-agreement/) for portal services | Numbers + credit |
| ME | Maine Secretary of State (maine.gov/sos) | Maine.gov [disclaimer](https://www.maine.gov/portal/policies/disclaimer.html) and [linking policy](https://www.maine.gov/portal/policies/linking.html): no framing, no presenting content as your own, no implied endorsement. [1 MRSA §538](https://mainelegislature.org/statutes/1/title1sec538.html): public information made available through InforME is owned by the public, and no copyright or licensing restriction may be placed on it | Numbers + credit, no framing |
| OH | Ohio SOS live results (liveresults.ohiosos.gov) | No terms page found. The [SOS privacy statement](https://www.ohiosos.gov/privacy-statement) says most SOS records are public records. **On 2026-11-02 the site served a JavaScript/cookie security check to a plain HTTP client** | Do not bypass. Use what a normal browser session or official downloads give, at modest intervals |
| MI | Michigan Bureau of Elections (michigan.gov; results host) | The most restrictive of the six. [Michigan.gov Policies](https://www.michigan.gov/policies): "You may not modify, copy, distribute, display, reproduce ... unless the law otherwise provides or the State gives you prior written permission". Commercial duplication, or use "likely to give the impression of official approval", is prohibited; framing is barred. The Great Seal is restricted by statute (MCL 2.45, 2.46, 750.245) | Facts and public records fall under "unless the law otherwise provides". Take numbers only: no layout, seal or framing, no implied approval |

- **Census shapes and federal data.** These are works of the US government and so in the public domain (17 U.S.C. 105). Credit "US Census Bureau".
- **Certified past results.** These are state public records; credit the publisher, as `baseline` already does.

### 1c. Exit polls and VoteCast: do not use

- Edison Research's exit polls, for the National Election Pool (ABC, CBS, CNN, NBC), and AP VoteCast are proprietary surveys licensed to subscribers.
- Individual findings quoted in a news story are facts, but they are the most hot-news-like data on election night: costly, time-sensitive and sold. Early waves are also unweighted and often misleading.
- AP itself won't call a race at poll close if VoteCast suggests a departure from long-running patterns ([Fox TV/AP explainer](https://fox10phoenix.com/news/polls-just-closed-how-can-ap-already-declare-winner-how-process-works)). That shows these surveys feed calls, which we never make.
- **Rule 12: none at all**, including AP's "expected vote" estimates, which are also proprietary.

### 1d. Candidate photos

- Works made by federal employees in their duties are public domain (17 U.S.C. 105).
- The [unitedstates/images](https://github.com/unitedstates/images) project takes member photos from the GPO Member Guide and reports that "GPO has assured us that all photos are public domain". Use this for sitting senators and House members who are candidates.
- An archived [Bioguide copyright notice](https://www.webharvest.gov/congress110th/20081212021638/http://bioguide.congress.gov/copyright.htm) warns that some images may be copyrighted. Prefer the GPO set, and keep a record of each photo's source.
- Challengers have no official portrait. Campaign photos, news photos and state-government photos (state works can be copyrighted) are not free.
- Wikimedia Commons is acceptable only for files with a clear public-domain or CC licence; show the credit (CC BY-SA needs author, licence and link). If one candidate has no usable image, Rule 15 (parity) means no photos in that race.

### 1e. Looking like a network: trade dress and marks

**The law**
- The Lanham Act protects registered marks (15 U.S.C. 1114). Section 43(a) (15 U.S.C. 1125(a)) also protects unregistered names and trade dress against confusion about source or affiliation.
- Distinctive trade dress can be protected (*Two Pesos v. Taco Cabana*, 505 U.S. 763 (1992)). Functional features cannot (*TrafFix Devices v. Marketing Displays*, 532 U.S. 23 (2001)).
- Red/blue party colours, choropleth maps, vote bars, check marks, "% reporting" and balance-of-power bars are common, functional conventions that anyone may use.
- What is risky: a network's names, logos, typefaces, bug and banner designs and specific colour scheme, together.
- YouTube's [impersonation policy](https://support.google.com/youtube/answer/2801947) independently bars copying an entity's "branding ... or specific color schemes".

**Names and marks to avoid.** Registration was checked for one mark only; avoid all of these regardless.

| Avoid | Associated with | Safe generic |
|---|---|---|
| "Key Race Alert", any "... ALERT" banner, "Breaking News" sirens | CNN (also Fox "Fox News Alert") | "Race update", "Results update" |
| "Magic Wall" | CNN | "Results map", "County map" |
| "Election Night in America", "America's Choice 2026", "Election Center" | CNN | "Election night 2026" |
| "America's Election Headquarters", "America's Election HQ" (USPTO Reg. No. 2,557,857, [Justia](https://trademark.justia.com/759/21/america-s-election-75921949.html)), "Democracy 2026" | Fox News | "2026 Senate results" |
| "Decision Desk", "Decision Desk HQ", "Fox News Decision Desk", "NBC News Decision Desk" | DDHQ / Fox / NBC | "Race calls: The Associated Press" |
| "Decision 2026", "Decision Night in America", "Big Board" | NBC / MSNBC | "Senate results", "Results board" |
| "Your Voice, Your Vote" | ABC | n/a |
| "America Decides", "Battleground Tracker" | CBS | n/a |
| "The Needle", "VoteCast", the AP logo, network logos, network typefaces and bugs | NYT / AP / all | Text attribution only |

**Generic terms that are fine:** "Balance of power", "Senate control", "Polls closed", "Votes counted", "Leading", "Unofficial results", "Too early to call". Use "too early to call" only attributed: "AP: too early to call", or our own "No AP declaration yet".

---

## 2. Election and campaign law

### 2a. FEC press (media) exemption

- **Statute and rules.** 52 U.S.C. 30101(9)(B)(i); 11 CFR 100.73 (not a contribution) and 100.132 (not an expenditure). The costs of "covering or carrying a news story, commentary, or editorial" by a broadcaster, website, newspaper, magazine or other periodical, "including any Internet or electronic publication", are exempt. The exception is an outlet owned or controlled by a party, political committee or candidate.
- **Two-step test.** Courts and the FEC ask (1) whether the entity is a press entity, and (2) whether it is acting in its legitimate press function. Factors include whether the material is available to the general public and comparable in form to what the outlet normally publishes, and whether a party, committee or candidate owns or controls it.
  - Cases: *Reader's Digest Ass'n v. FEC*, 509 F. Supp. 1210 (S.D.N.Y. 1981); *FEC v. Phillips Publishing*, 517 F. Supp. 1308 (D.D.C. 1981).
  - FEC guidance: [AO 2016-01](https://www.fec.gov/updates/ao-2016-01-websites-distribution-of-news-content-to-users-qualifies-for-media-exemption/).
- **Online outlets qualify.** The 2006 Internet rules (71 Fed. Reg. 18589) made this explicit. The FEC has applied the exemption to websites ([AO 2005-16](https://www.fec.gov/updates/advisory-opinion-2005-16-press-exception-applied-to-web-sites)) and to webcast video (AO 2000-13, iNEXTV). FEC guidance treats bloggers like traditional media.
- **Our stream** is a publicly available, regularly produced news programme, owned by no candidate, party or committee. It fits.
- **A second, independent basis.** An unpaid YouTube stream is not a "public communication": 11 CFR 100.26 excludes internet communications other than ads placed for a fee on another's site. Individuals' uncompensated internet activity is also exempt (11 CFR 100.94, 100.155).

### 2b. What would take us outside

- **Express advocacy.** 11 CFR 100.22: explicit words ("vote for", "re-elect", "support", "defeat", "reject"), or a message with no reasonable reading other than urging a candidate's election or defeat.
  - A genuine press entity's editorials are exempt even so. But advocacy is exactly what costs the "legitimate press function" factor, and it would also breach YouTube's and our own neutrality rules. Rule 19.
- **In-kind contribution.** Anything of value given to a campaign (11 CFR 100.52(d)): producing content for a campaign, or coordinating content with one (11 CFR 109.20-109.21). Republishing campaign materials is also covered (11 CFR 109.23), with a bona fide news exception at 109.23(b)(4); we don't need it. Rules 20-21.
- **Paid promotion** by a campaign or PAC would make a segment a political ad, needing FEC disclaimers (11 CFR 110.11) and YouTube's paid-promotion flag. Refuse all of it.

### 2c. Foreign nationals

- The ban covers foreign-national contributions, donations, expenditures, independent expenditures and electioneering communications, plus foreign nationals directing such decisions (52 U.S.C. 30121; 11 CFR 110.20, including (i)).
- It was upheld in *Bluman v. FEC*, 800 F. Supp. 2d 281 (D.D.C. 2011), aff'd, 565 U.S. 1104 (2012). The court stressed that foreign nationals remain free to speak about politics in ways that are not contributions or express advocacy.
- Neutral, exempt news coverage is neither a contribution nor an expenditure, so the ban is not triggered, even if team members are non-citizen students or viewers are abroad.
- Viewers' Super Chats pay the channel, not any campaign.
- **Conservative rule:** no advocacy, no money to or from campaigns, and no foreign national on the team directing anything that could be advocacy.

### 2d. Equal time and fairness: not applicable

- 47 U.S.C. 315(a) (equal opportunities) binds broadcast station *licensees*; 47 CFR 76.205 extends it to cable origination. A YouTube channel is neither.
- Even for broadcasters, bona fide newscasts and on-the-spot news coverage are exempt (315(a)(1)-(4)).
- The FCC abandoned the Fairness Doctrine in *Syracuse Peace Council*, 2 FCC Rcd 5043 (1987), aff'd, 867 F.2d 654 (D.C. Cir. 1989), and deleted the rules in 2011.
- **Confirmed: no equal-time or fairness obligation applies.** Our balance rules (s7) are editorial policy and YouTube risk management.

---

## 3. AI and synthetic-media election laws (in force on 2026-11-03)

Every law below targets either paid political advertising or deceptive depictions of a real person (making a candidate appear to say or do something). None covers a disclosed synthetic narrator reading official counts that depicts no real person's speech or conduct. The conservative build rules (23-26) keep it that way.

| Jurisdiction | Law in force | Covers | Our stream |
|---|---|---|---|
| Federal: FEC | No AI rule. [Interpretive rule, 89 Fed. Reg. 78785 (Sept 26, 2024)](https://regulations.justia.com/regulations/fedreg/2024/09/26/2024-21983.html): fraudulent misrepresentation of campaign authority (52 U.S.C. 30124; 11 CFR 110.16) applies "irrespective of the technology used", AI included. The FEC declined to open an AI rulemaking | Pretending to speak for a candidate or party | Not covered (we never purport to speak for anyone) |
| Federal: FCC | Feb 2024 declaratory ruling (FCC 24-17): AI voices in robocalls are "artificial voice" under the TCPA. Political-ad AI disclosure NPRM (MB Docket 24-211, July 2024) was never adopted, and would have covered only broadcast and cable ads | Robocalls; broadcast ads | Not covered |
| Federal: Congress | No enacted statute found. S. 2770 (Protect Elections from Deceptive AI Act) and S. 3875 (AI Transparency in Elections Act) were reported from committee in May 2024 and not enacted ([Akin tracker](https://www.akingump.com/en/insights/ai-law-and-regulation-tracker/Senate-Rules-Committee-Reports-Election-Related-AI-Bills-Out-of-Committee)) | n/a | n/a |
| **Texas** | [Tex. Elec. Code 255.004(d)-(e)](https://codes.findlaw.com/tx/election-code/elec-sect-255-004/): creating a "deep fake video" (made "with the intent to deceive", appearing to depict a real person "performing an action that did not occur") with intent to injure a candidate or influence the result, and causing it to be published within 30 days of an election. Class A misdemeanor. 255.004(b) (true-source) was held unconstitutional in *Ex parte Stafford*, No. PD-0310-23 (Tex. Crim. App. Sept 2024). 2025 bills all died: HB 366 (altered-media ad disclosure) passed the House 4/30/2025 with no Senate action ([TLO](https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill=HB366)); HB 401 left in committee ([TLO](https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill=HB401)); HB 556 and SB 893 died | Deceptive video of a real person | Not covered: no video of any real person; the TTS voice is no one's |
| **Michigan** | [MCL 169.259](https://legislature.mi.gov/Laws/MCL?objectName=mcl-169-259) (2023 PA 263, eff. Feb 13, 2024): a paid "qualified political advertisement" with AI-generated content must say so. [MCL 168.932f](https://legislature.mi.gov/Laws/MCL?objectName=mcl-168-932f) (HB 5144 of 2023): distributing AI "materially deceptive media" that falsely depicts someone saying or doing something, within 90 days of an election, knowingly and with intent to harm a candidate or deceive voters. Misdemeanor, unless the media carries a "manipulated by technical means" disclaimer | Paid ads; false depictions of a person | Not covered (unpaid news, no depiction). Rule 25 keeps it so |
| **Maine** | LD 517, P.L. 2025 c. 593 (signed Mar 2026; reported effective Jul 29, 2026). Adds 21-A MRSA §1014(5-C): a "public communication" that already needs a §1014 paid-for disclosure and contains synthetic media must state "THIS COMMUNICATION CONTAINS AUDIO, VIDEO AND/OR IMAGES THAT HAVE BEEN MANIPULATED OR ALTERED". Fines up to 500% of the spend. Exemptions for satire, newscasts and documentaries, and outlets paid to carry it ([Maine Wire](https://www.themainewire.com/2026/03/maine-senate-advances-disclosure-requirement-for-ai-altered-campaign-materials-along-partisan-lines/), [committee amendment](https://lldc.mainelegislature.org/Open/LDs/132/132-LD-0517-CA_A_H837.pdf)) | Paid campaign communications with synthetic media of candidates | Not covered (no paid communication; news). Enacted text not retrieved, so the effective date is as reported |
| **Alaska** | None. SB 64 (an election omnibus with deepfake disclosure) was vetoed Apr 30, 2026, and the override failed 38-22 on May 4, 2026 ([KTOO](https://www.ktoo.org/2026/05/04/veto-override-vote-on-elections-bill-fails-as-two-southeast-alaska-lawmakers-flip/), [Governor](https://gov.alaska.gov/governor-vetoes-senate-bill-64-due-to-its-numerous-legal-operational-concerns/)) | n/a | n/a |
| **Kansas** | None. HB 2559 and SB 375 (2024) died; Kansas is one of 19 states without AI political-ad rules ([Axios, Oct 29, 2026](https://www.axios.com/local/kansas-city/2026/10/29/ai-political-ads-kansas-missouri-no-rules)) | n/a | n/a |
| **Ohio** | None enacted ([Ballotpedia](https://ballotpedia.org/AI_deepfake_policy_in_Ohio); [Ohio Capital Journal, May 18, 2026](https://ohiocapitaljournal.com/2026/05/18/why-ohio-doesnt-have-any-artificial-intelligence-regulations/)). HB 185 (AI political-ad disclaimers) and SB 163 (deepfakes) are pending. Ohio's old false-statement law was struck in *Susan B. Anthony List v. Driehaus*, 814 F.3d 466 (6th Cir. 2016) | n/a | n/a |
| California (context) | AB 2839 (deceptive election content) permanently enjoined as facially unconstitutional, Aug 2025 (*Kohls v. Bonta*, E.D. Cal. No. 2:24-cv-02527). AB 2655 (platform duties): state barred by stipulated order from enforcing it against platforms ([summary](https://regulations.ai/enforcement/lit-stateofcalifornia-20250829)). AB 2355 (AI disclosure in committee ads) applies to ads only | Ads; platforms | Not covered |
| EU (Spanish-speaking viewers in Spain) | [EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) Art. 50(4), applying from Aug 2, 2026 and not delayed by the 2026 Digital Omnibus ([CSA note](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-article-50-transparency-20260729/)). Deployers must disclose deepfakes, and AI-generated *text* "published with the purpose of informing the public on matters of public interest", unless it is human-reviewed under someone's editorial responsibility. Art. 2(1)(c) reaches non-EU deployers whose output is used in the EU | AI-written news text; deepfakes | **Arguably covered.** Satisfied by Rule 23: the disclosure must say *AI-written*, not only "AI voice" |

**Bottom line.** No featured-state or federal law requires anything of this stream. YouTube's disclosure rule (s6b) and, for EU viewers, AI Act Art. 50(4) are the binding disclosure duties. Both are met by Rules 23-24.

---

## 4. Reporting results before polls close

- **No federal law** bars media from reporting returns or projections before polls close. Congress likely could not ban it: CRS, [*Election Projections: First Amendment Issues*, RS20762 (2001)](https://www.everycrsreport.com/reports/RS20762.html).
- Exit polling near polling places is protected speech: *Daily Herald Co. v. Munro*, 838 F.2d 380 (9th Cir. 1988).
- State laws regulate when *officials* may release counts, not what media may say.
- **Voluntary practice.**
  - Since the 1980s the networks have pledged not to project a state before its polls close; a 1985 understanding with Congress covered "most" polls ([CBS, Nov 21, 2000](https://www.cbsnews.com/news/why-network-calls-were-wrong)). After Florida 2000, where calls came while the Central-time Panhandle was still voting, network executives pledged at the Feb 14, 2001 House Energy & Commerce hearing to wait until *all* polls in a state close ([hearing record](https://www.govinfo.gov/content/pkg/CHRG-107hhrg71490/html/CHRG-107hhrg71490.htm); [RCFP](https://www.rcfp.org/networks-answer-congress-election-night-coverage/)).
  - AP does not call before a jurisdiction's last polls close ([HPR/AP](https://www.hawaiipublicradio.org/national-international/2022-11-08/explainer-how-can-the-associated-press-call-races-right-as-polls-close)).
- **Our rule (27-29)** is stricter than the networks'. Show no numbers or characterisation for a state until its *last* polls close, even if a county posts early.
  - Alaska's Division of Elections plans to post first results at 8:45-9:00 pm Alaska time, which is 12:45-1:00 am ET and *before* the western Aleutians close at 1:00 am ET. We wait until 1:00 am ET.
  - Voters in line at closing may still vote; that does not delay our rule.

**Poll-closing times, Tue Nov 3, 2026, in ET** (local hours per state law; zones per [watch.vote](https://watch.vote/midterms/2026/poll-closing-times) and [Election Central](https://www.uspresidentialelectionnews.com/2026/11/what-time-do-polls-close-2026-midterm-election/)):

| State | First close (ET) | Last close (ET) = characterise from | Detail |
|---|---|---|---|
| OH | 7:30 pm | **7:30 pm** | 6:30 am-7:30 pm statewide (R.C. 3501.32) |
| ME | 8:00 pm | **8:00 pm** | Polls close 8 pm (21-A MRSA §626); some tiny towns may close earlier |
| TX | 8:00 pm | **9:00 pm** | 7 am-7 pm local (Elec. Code 41.031). Central-time counties close 8 pm ET; **El Paso and Hudspeth** (Mountain) close 9 pm ET |
| KS | 8:00 pm | **9:00 pm** | [K.S.A. 25-106](https://www.ksrevisor.gov/statutes/chapters/ch25/025_001_0006.html). Central counties: 7 am-7 pm CT, extendable to 8 pm CT (= 9 pm ET). Mountain counties (**Greeley, Hamilton, Sherman, Wallace**): default 6 pm MT (8 pm ET), extendable to 7 pm MT (= 9 pm ET), never later |
| MI | 8:00 pm | **9:00 pm** | 7 am-8 pm local (MCL 168.720). Central-time UP counties **Gogebic, Iron, Dickinson, Menominee** close 9 pm ET |
| AK | 12:00 am Wed | **1:00 am Wed** | 7 am-8 pm local. Mainland 8 pm AKST = 12:00 am ET; **Aleutians west of 169°30′W** (Hawaii-Aleutian time) 8 pm HAST = 1:00 am ET |

Times are for scheduled closing. Treat a court-ordered extension in any county (posted by the state) as moving that state's time.

---

## 5. Defamation, accuracy, ranked choice

### 5a. Candidate backgrounds and positions

- **Who is liable.** Candidates are public figures. Defamation needs a false statement of fact made with actual malice, that is knowing falsity or reckless disregard: *New York Times v. Sullivan*, 376 U.S. 254 (1964); *Monitor Patriot Co. v. Roy*, 401 U.S. 265 (1971), which applies this to candidates and to anything relevant to fitness for office.
- **No Section 230 shield.** Section 230 (47 U.S.C. 230(c)(1)) protects only third-party content. LLM-written scripts we publish are *our* content.
- **The real risk is fluent hallucination.** Publishing unverified model output about a person could be argued to be reckless disregard. The facts must therefore come from records.
- **What to do (Rules 30-34):**
  - Use a closed fact set per candidate, each fact with a source URL: official bio, congress.gov votes, the state ballot listing, the candidate's own site and statements, government records.
  - The writer may only rephrase card facts, and QC checks every claim against the card.
  - Attribute positions ("says", "according to her campaign website"). Paraphrase neutrally rather than adopting campaign slogans; put a candidate's wording in quotation marks.
  - Leave out allegations, legal matters, investigations, scandals, health, family and opponents' claims; none are in scope.
  - Check names, titles and offices (for example, the Ohio seat is the special election for the seat Vance vacated).
  - Corrections are visible.
- Some states' "false statements about candidates" laws have been struck down, such as Ohio's in *SBA List v. Driehaus* (above). This does not lower our standard.

### 5b. Ranked-choice voting: what we may say on election night

**Maine (RCV applies to the US Senate general election)**
- **Statute.** [21-A MRSA §723-A(2)](https://legislature.maine.gov/statutes/21-A/title21-Asec723-A.html): a candidate ranked first "on more than 50% of all ballots cast for the particular office ... including ... ballots on which ranking number one is blank, on which there is an overvote ..." is declared the winner.
- **Otherwise** the count runs in rounds. The last-place candidate is eliminated each round; exhausted ballots drop out; with two candidates left, the one with more votes wins.
- **The denominator includes blank ballots.** So 50.3% of candidate votes can still be under 50% of ballots cast.
- **Write-ins.** Declared write-in candidates make the race a multi-candidate RCV contest. States Newsroom reported two ballot-listed candidates plus six declared write-ins, and the Secretary of State thinks a runoff is likely.
- **Timing.** Results arrive town by town. If needed, the RCV count happens centrally in Augusta, and the Secretary of State expects it to last "until at least the Friday of the week following Election Day" (Oct 21, 2026 report, [newsfromthestates](https://www.newsfromthestates.com/article/outcome-maines-us-senate-race-may-not-be-known-weeks-heres-why)).
- **May say:**
  - "first-choice votes"
  - "X leads in first-choice votes"
  - "To win outright, a candidate must be ranked first on more than half of all ballots cast for Senate, including blank ones"
  - "If no one does, the Secretary of State will run the ranked-choice count in Augusta, likely next week"
  - "AP has declared ..." (only if AP does)
- **May not say:**
  - that anyone "has a majority" or that "there will / won't be a runoff" on our own arithmetic
  - any projection of second-choice transfers or who "would win" the RCV count
  - "runoff election" (no new election is held; say "ranked-choice count")

**Alaska (top-four primary on Aug 18, 2026; RCV general)**
- **Statute.** Under AS 15.15.350, a candidate highest-ranked on *more than half of the active ballots* wins; otherwise the count runs in rounds.
- **Denominator differs from Maine.** Active ballots exclude exhausted and blank ballots.
- **Election night.** The Division of Elections reports first-choice results only during the absentee window ([FairVote](https://fairvote.org/press/fact-sheet-alaskas-2026-ranked-choice-voting-elections/)). Ballots postmarked by Nov 3 keep arriving (AS 15.20.081).
- **Dates.** RCV tabulation is on **Nov 18**; certification is targeted for **Nov 25** ([Alaska Public Media, Oct 5, 2026](https://alaskapublic.org/news/politics/elections/2026-10-05/what-to-know-about-alaskas-general-election)).
- **Ballot Measure 2** (on this ballot) would repeal top-four and RCV for *future* elections ([Ballotpedia](https://ballotpedia.org/Alaska_Repeal_Top-Four_Ranked-Choice_Voting_Initiative_(2026))). It does not affect this count. It is outside the Senate scene, so mention it only neutrally, if at all.
- **May say:**
  - "first-choice votes"
  - "X leads in first-choice votes"
  - "Absentee ballots postmarked by election day are still arriving"
  - "If no candidate has more than half of the active ballots, the ranked-choice tabulation will be on November 18"
  - party labels exactly as printed on the ballot ("registered Republican", "Nonpartisan", "Undeclared")
- **May not say:**
  - an RCV outcome
  - "X wins" on first choices (unless AP declares)
  - that a party label means the party nominated the candidate (top-four is nonpartisan)

---

## 6. YouTube policies for this stream

### 6a. Elections misinformation ([policy](https://support.google.com/youtube/answer/10835034); [misinformation policies](https://support.google.com/youtube/answer/10834785))

- **Prohibited:**
  - voter suppression (misleading claims about the time, place, means or eligibility for voting)
  - false claims about candidates' eligibility (age, citizenship, death)
  - incitement to interfere with democratic processes
  - technically manipulated content that misleads with serious risk of harm
- **Enforcement.**
  - A first violation usually brings a warning; three strikes in 90 days can terminate the channel.
  - Strikes are channel-wide, so they would also hit the weather streams.
  - Posting and live streaming are blocked for one week on the first strike and two weeks on the second ([strike basics](https://support.google.com/youtube/answer/2802032)).
- **Advertiser-friendly guidelines** put demonstrably false claims that undermine trust in elections in the no-ads category.
- Rules 22 and 44 keep us far from all of this.

### 6b. Altered or synthetic content disclosure

- **Requirement.** YouTube requires disclosure of realistic AI-generated or altered content ([help](https://support.google.com/youtube/answer/14328491)).
- **Synthetic narration counts.** YouTube's launch post lists "synthetically generating a person's voice to narrate a video" as needing disclosure ([YouTube blog, Mar 2024](https://blog.youtube/news-and-events/disclosing-ai-generated-content/)).
- **Not needed for** AI-written scripts alone, captions or clearly unrealistic content.
- **Labels.** For sensitive topics, explicitly including news and elections, the label appears **on the player itself**, not only in the description. Disclosure alone "won't limit a video's audience or impact its eligibility to earn money". Consistently failing to disclose can lead to a forced label, removal or YPP suspension.
- **API.**
  - `status.containsSyntheticMedia` (boolean) exists on the **`videos`** resource and is settable in `videos.insert` and `videos.update` ([videos resource](https://developers.google.com/youtube/v3/docs/videos); [revision history, Oct 30, 2024](https://developers.google.com/youtube/v3/revision_history)).
  - The **`liveBroadcasts`** resource has no such field. Its `status` holds `lifeCycleStatus`, `privacyStatus`, `recordingStatus`, `madeForKids` and `selfDeclaredMadeForKids` ([liveBroadcasts](https://developers.google.com/youtube/v3/live/docs/liveBroadcasts)).
  - A broadcast's id *is* its video id, so call `videos.update(part="status")` on the broadcast id. Resend the other writable status fields (`privacyStatus` etc.), or they reset.
  - `src/broadcast/youtube.py` already does this. Make sure the election script passes `synthetic=True`.
- **On-screen disclosure strings** (Rule 23; these also satisfy EU AI Act Art. 50(4)):
  - EN: "AI-written script, read by a synthetic voice. Unofficial results from state election offices. Not affiliated with any news organization, campaign or government."
  - ES: "Guion escrito con IA y leído por una voz sintética. Resultados no oficiales de las oficinas electorales estatales. Sin afiliación con ningún medio, campaña ni gobierno."
  - JA: "原稿はAIが作成し、合成音声で読み上げています。数字は各州選挙当局の非公式開票結果です。報道機関・陣営・政府とは無関係です。"
  - ZH (Traditional): "本節目由AI撰稿、合成語音播報。數據為各州選舉機關公布之非正式開票結果。與任何新聞機構、競選陣營或政府無關。"
  - ZH (Simplified): "本节目由AI撰稿、合成语音播报。数据为各州选举机构公布的非正式计票结果。与任何新闻机构、竞选阵营或政府无关。"

### 6c. Monetisation

- **Inauthentic content.** The [YPP policies](https://support.google.com/youtube/answer/1311392) renamed "repetitious content" to **"inauthentic content"** on **July 15, 2025**. Not monetisable: content that "looks like it's made with a template", "AI-generated content made with generic or unoriginal templates giving the impression of mass production", or content with minimal variation.
  - Fine: the same intro and outro, as long as the bulk differs.
  - A data-driven stream whose script changes with each update is original. Long identical loops are the risk (Rule 45).
- **No election-specific creator demonetisation** appears in the [advertiser-friendly guidelines](https://support.google.com/youtube/answer/6162278). Non-graphic news coverage is monetisable. "Incendiary and demeaning" content and false election claims are limited or get no ads.
- **Ad demand.** Google paused US *election ads* (advertiser side, including YouTube) after polls closed in 2020 and 2024 ([2024 report](https://searchengineland.com/google-to-pause-us-election-ads-after-polls-close-on-november-5th-447650)). Nothing found for 2026. It reduces ad demand but does not affect our eligibility.

### 6d. Metadata, thumbnails, impersonation

- **Spam and deceptive practices** ([policy](https://support.google.com/youtube/answer/2801973)): bars "maliciously misleading titles, thumbnails, descriptions" that trick users into clicking. A thumbnail or title showing a winner before AP declares, or claiming "official" results, is the obvious violation (Rule 43).
- **Impersonation** ([policy](https://support.google.com/youtube/answer/2801947)): bars deceptively copying an entity's branding, "profile pictures, banners, or specific color schemes", lookalike names, and adding "Official". This is the platform version of s1e.

### 6e. Live-stream rules

- Community Guidelines apply to live content in full. YouTube may restrict a channel's live streaming at its discretion; each channel may have 10 concurrent streams ([get started](https://support.google.com/youtube/answer/2474026); [avoid restrictions](https://support.google.com/youtube/answer/2853834)).
- Live streams are scanned for third-party content. A match can replace the stream with a placeholder or end it ([copyright and live](https://support.google.com/youtube/answer/3367684)). Never carry network or AP audio or video (Rule 17).

### 6f. YouTube's own election panels

- YouTube shows candidate panels in search, voting-information panels and, for "select national elections", **election-results panels** under election videos, linking to third-party sources ([help](https://support.google.com/youtube/answer/10047535)).
- In 2022 the US results panel linked to Google's AP-powered results and warned that results may not be final ([YouTube blog 2022](https://blog.youtube/news-and-events/the-2022-us-midterm-elections-on-youtube/)). No 2026 announcement found; expect a similar panel under our stream.
- If the panel shows AP results while our screen shows only official counts, the two can differ. On-screen labels must say "official count", and the AP call rule stays as written.

### 6g. Rules specific to Japan, Taiwan and Spanish-language audiences

**Checked: none affect a US-election results stream.**
- **Japan.** The Public Offices Election Act governs Japanese elections only. The Broadcasting Act's political-fairness duty (Art. 4) binds Japanese licensed broadcasters, not YouTube channels. The 2025 AI Promotion Act imposes no labelling duty.
- **Taiwan.** The election and recall laws, including their deepfake provisions, and the Anti-Infiltration Act concern Taiwan's own elections and politics.
- **PRC.** The 2025 AI-labelling measures apply to services offered in the PRC, and YouTube is blocked there.
- **EU/Spain.** AI Act Art. 50(4) (s3) is the one that arguably reaches us; it is met by the disclosure.
- **Latin America.** Not researched in depth; no rule aimed at foreign-election coverage is known.
- **YouTube's policies are global.**
- **One practical item:** in Taiwan, blue and green mean KMT and DPP (Rule 42).

---

## 7. Neutrality: script do / don't

**Results language**
- Say only "leads", "is ahead", "trails", "is behind by N votes / N points".
- Always "in the official count so far", or "first-choice votes" in ME and AK.
- Never "winning", "losing", "on track", "poised", "favoured", "safe", "lean" or "in trouble".
- After an AP call only: "AP has declared X the winner". "Won" or "defeated" may appear only in that attributed sentence.
- Say "conceded" only when a news report says so, and attribute it.

**Parties and candidates**
- **Labels:** "the Republican nominee / Republican X", "the Democratic nominee / Democrat X". Independents and third parties exactly as the ballot lists them ("independent", "Libertarian", "Green", Alaska "Nonpartisan" / "Undeclared").
- **Caucus facts only as facts** ("an independent who caucuses with Democrats").
- **No ideological labels** from us: no "moderate", "centrist", "progressive", "conservative firebrand", "MAGA", "establishment". A label may appear only as the candidate's attributed self-description, and the same field must exist for every candidate.
- **Balance:**
  - Same card fields for each candidate.
  - Sentence count within ±1 (Rule 40).
  - Order: ballot order or alphabetical for profiles, count order for results; alternate who is named first across beats.
  - Same photo treatment for everyone.
  - Current senators: identical fields (name, party, since, term ends, seat up / not up).
- **Positions:** attributed and paraphrased in neutral terms, for example:
  - "supports abortion rights" / "supports restrictions on abortion" (not pro-life or pro-choice)
  - "immigrants in the country illegally" (not "illegal aliens")
  - "Affordable Care Act" (not "Obamacare")
- **Counties and history:** numbers only ("Harris County voted 52% for Harris in 2024").

**Banned in our own voice in every language** (QC regex plus an LLM check). Quoted, attributed candidate speech is not used at all (Rule 25), so there is no exception.

| Concept | EN | ES | JA | ZH (Trad / Simp) |
|---|---|---|---|---|
| Landslide / crushing | landslide, crushing, crushes, routs, trounces, blowout, sweeps, wipeout, rout | aplastante, arrollador, paliza, arrasa, barre, victoria contundente, debacle, batacazo | 圧勝, 大勝, 地滑り的, 惨敗, 完敗, 楽勝, 大敗 | 壓倒性勝利/压倒性胜利, 大勝/大胜, 慘敗/惨败, 輾壓/碾压, 橫掃/横扫, 完勝/完胜 |
| Drama / surprise | stunning, shocking, upset, comeback, collapse, nail-biter, bloodbath, historic (as hype) | impactante, sorpresa, remontada, colapso, histórico (como énfasis) | 衝撃, 激震, 番狂わせ, 大逆転, 崩壊, 歴史的 (as hype) | 震撼, 爆冷, 大逆轉/大逆转, 翻盤/翻盘, 崩盤/崩盘 |
| Waves | red wave, blue wave, red/blue tsunami | ola roja, ola azul | 赤い波, 青い波 | 紅潮/红潮, 藍潮/蓝潮, 紅色浪潮 |
| Extremes | far-right, far-left, radical, extremist, fringe, hardliner | ultraderecha, extrema derecha, extrema izquierda, radical, extremista, ultra | 極右, 極左, 過激派, 急進派, 強硬派 | 極右/极右, 極左/极左, 激進/激进, 極端分子/极端分子, 強硬派/强硬派 |
| Labels as epithets | socialist, communist, fascist, MAGA, RINO, woke, elite, establishment | socialista, comunista, fascista, "woke", élite | 社会主義者, 共産主義者, ファシスト, エリート | 社會主義者/社会主义者, 共產/共产, 法西斯, 菁英/精英 |
| Fraud / legitimacy | stolen, rigged, fraud, cheating, illegitimate, suppression, "election denier" | robada, amañada, fraude, trampa, ilegítima | 不正選挙, 盗まれた, 操作された, 不正, 正当性がない | 舞弊, 作弊, 做票, 被偷走, 操縱/操纵, 不合法 |
| Our own call | projected, will win, has won, is the winner (without AP), presumptive, safe seat | proyectado, ganará, ganó (sin AP), virtual ganador | 当確/当選確実 (unless "AP通信は…と伝えました"), 勝利確実, 優勢, 安泰 | 當選/当选 (unless "美聯社宣布"), 穩贏/稳赢, 凍蒜/冻蒜, 篤定/笃定, 勝券在握 |
| Loaded descriptors | embattled, controversial, disgraced, beleaguered, firebrand, puppet | polémico, cuestionado, títere | 問題の, 物議を醸す, 傀儡 | 爭議/争议, 備受爭議, 傀儡 |
| Party slurs / terms | "Democrat Party", "Dems/GOP" as slang in Spanish/Asian scripts | "demócratas radicales", "republicanos extremistas" | 「民主党左派」等のレッテル | 藍營/綠營 (for US parties), 白左, 川粉 |

**Preferred vocabulary**
- **ES:** "aventaja / va adelante / lidera el conteo oficial", "va por detrás / queda a N votos", "Partido Republicano / Partido Demócrata", "candidato independiente".
- **JA:** "リードしています / 上回っています", "N票差で追っています / 下回っています", "共和党 / 民主党 / 無所属".
- **ZH:** "領先 / 领先", "落後 / 落后 N 票", "共和黨 / 民主黨" (Trad) and "共和党 / 民主党" (Simp), "無黨籍 / 独立候选人".

**No predictions, no meta-judgement.** No "this race will decide control of the Senate"; say instead "51 seats are needed for a majority; currently ...". No "momentum", no "must-win", and no adjectives about turnout ("huge", "disappointing").

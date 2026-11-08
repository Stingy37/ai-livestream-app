"""AP race-call candidate matcher, monitor and confirm/retract (src/election/calls.py).

Positive headlines are the real 2024 AP Senate race-call stories as SearXNG returned them on 2026-11-03 (titles truncated
by the search engines, with their apnews.com URLs), plus full forms; they are matched against a 2024 roster. 2026 forms
(names from data/election/races.json) follow the same templates. Negatives are real 2024 / 2026 headlines that must
not count as a Senate general-election call (governor, House, primaries, live blogs, forecasts) and synthetic tricky
ones (nomination, runoff, opinion, questions, conditionals, wrong party, wrong state, ambiguous name).
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from election import calls as K

ET = dt.timezone(dt.timedelta(hours=-5))
R26, CLOSE26 = K.load_roster()

ROSTER_2024 = {"senate_races": [
    {"state": st, "poll_close_et": "2024-11-05T20:00:00-05:00",
     "nominees": [{"key": k, "name": n, "party": p} for k, n, p in cands]}
    for st, cands in {
        "PA": [("mccormick", "Dave McCormick", "REP"), ("casey", "Bob Casey", "DEM")],
        "DE": [("bluntrochester", "Lisa Blunt Rochester", "DEM"), ("hansen", "Eric Hansen", "REP")],
        "IN": [("banks", "Jim Banks", "REP"), ("mccray", "Valerie McCray", "DEM")],
        "MI": [("slotkin", "Elissa Slotkin", "DEM"), ("rogers", "Mike Rogers", "REP")],
        "MT": [("sheehy", "Tim Sheehy", "REP"), ("tester", "Jon Tester", "DEM")],
        "AZ": [("gallego", "Ruben Gallego", "DEM"), ("lake", "Kari Lake", "REP")],
        "OH": [("moreno", "Bernie Moreno", "REP"), ("brown", "Sherrod Brown", "DEM")],
        "TX": [("cruz", "Ted Cruz", "REP"), ("allred", "Colin Allred", "DEM")],
        "CA": [("schiff", "Adam Schiff", "DEM"), ("garvey", "Steve Garvey", "REP")],
        "NV": [("rosen", "Jacky Rosen", "DEM"), ("brown", "Sam Brown", "REP")],
        "NH": [("shaheen", "Jeanne Shaheen", "DEM")],
        "MD": [("alsobrooks", "Angela Alsobrooks", "DEM"), ("hogan", "Larry Hogan", "REP")],
    }.items()]}


@pytest.fixture(scope="module")
def r24(tmp_path_factory):
    p = tmp_path_factory.mktemp("r") / "races2024.json"
    p.write_text(json.dumps(ROSTER_2024))
    return K.load_roster(p)[0]


AP = "https://apnews.com/article/"

# (title as returned by the search engine, url, expected (state, key), form)
AP_2024_POSITIVE = [
    ("AP Race Call: Republican Dave McCormick wins election to U.S. Senate ...",
     AP + "race-call-mccormick-wins-pennsylvania-senate-49bdac09ba654d07b88bc62b10b49154", ("PA", "mccormick")),
    ("AP Race Call: Democrat Lisa Blunt Rochester wins election to U.S. ...",
     AP + "race-call-blunt-rochester-wins-delaware-senate-5464ee00ac7e49968fee745be6c653cf", ("DE", "bluntrochester")),
    ("AP Race Call: Republican Jim Banks wins election to U.S. Senate ...",
     AP + "race-call-banks-wins-indiana-senate-15bcb1fb22fc47709522ea0d16dcd8af", ("IN", "banks")),
    ("AP Race Call: Democrat Elissa Slotkin wins election to U.S ...",
     AP + "race-call-slotkin-wins-michigan-senate-b17c69f073674ec38cf7cad7f7af4f9d", ("MI", "slotkin")),
    ("AP Race Call: Republican Tim Sheehy wins election to U.S ...",
     AP + "race-call-sheehy-wins-montana-senate-651c3addae78438f9de1e0ff6eedd947", ("MT", "sheehy")),
    ("AP Race Call: Democrat Ruben Gallego wins election to U.S ...",
     AP + "race-call-gallego-wins-arizona-senate-1e39cc57d665435fa816a3502619d29b", ("AZ", "gallego")),
    ("AP Race Call: Republican Bernie Moreno wins election to U.S ...",
     AP + "race-call-moreno-wins-ohio-senate-ae19f928aba2418da51f93089a843a64", ("OH", "moreno")),
    ("AP Race Call: Republican Ted Cruz wins reelection to U.S ...",
     AP + "race-call-cruz-wins-texas-senate-c7dfbc95d19d4253bbb4edb33f452587", ("TX", "cruz")),
    ("AP Race Call: Democrat Adam Schiff wins special election to U ...",
     AP + "race-call-schiff-wins-california-senate-688626bdf0f34a8489fc0a8c7cce0833", ("CA", "schiff")),
    # full (untruncated) forms of the same template
    ("AP Race Call: Republican Dave McCormick wins election to U.S. Senate in Pennsylvania, beating incumbent Bob Casey",
     AP + "race-call-mccormick-wins-pennsylvania-senate-49bdac09ba654d07b88bc62b10b49154", ("PA", "mccormick")),
    ("AP Race Call: Democrat Angela Alsobrooks wins election to U.S. Senate in Maryland, beating Larry Hogan | AP News",
     AP + "race-call-alsobrooks-wins-maryland-senate-0123456789abcdef0123456789abcdef", ("MD", "alsobrooks")),
    # AP's own news stories and explainers
    ("Democrat Elissa Slotkin wins Michigan’s open Senate seat ...",
     AP + "michigan-senate-slotkin-rogers-03884db9f8f2ff6d15be150f6c29ef14", ("MI", "slotkin")),
    ("Democrat Ruben Gallego wins Arizona US Senate race against ...",
     AP + "arizona-senate-ruben-gallego-kari-lake-ea364326c93f9a8a32b7b9ca7ca696d4", ("AZ", "gallego")),
    ("Republican Tim Sheehy defeats Jon Tester to win Montana US Senate seat",
     AP + "senate-election-tester-sheehy-montana-f882b50bf4af6a87ec32e3a5f626eccb", ("MT", "sheehy")),
    ("Why AP called the Michigan Senate race for Elissa Slotkin",
     AP + "michigan-senate-race-call-explain-rogers-slotkin-3e6ae97face22dc1d5f4e86c2fd09736", ("MI", "slotkin")),
    ("Why AP called the Montana Senate race for Republican Tim Sheehy",
     AP + "ap-race-call-explainer-montana-senate-7150caeefe2c0ff89b64eaddc328172b", ("MT", "sheehy")),
    ("Why AP called the Ohio Senate race for Bernie Moreno",
     AP + "ohio-senate-race-call-explain-brown-moreno-d5648d992474761fa87908f5cda2c213", ("OH", "moreno")),
]

AP_2024_NEGATIVE = [
    ("AP Race Call: Republican Kelly Ayotte wins election for ...",                      # governor (from the URL)
     AP + "race-call-ayotte-wins-new-hampshire-governor-2f35a2ddcffa404c9832114cc742ad65"),
    ("AP Race Call: Democrat April McClain Delaney wins election to U.S ...",            # House
     AP + "race-call-delaney-wins-maryland-u-s-house-district-1675c1cb5c6146b08c695f26d6017c6e"),
    ("Trump-backed Bernie Moreno wins Ohio’s GOP Senate primary ...",                     # primary
     AP + "election-2024-senate-ohio-moreno-larose-dolan-cffe7722ac68e79deebae8353dd2fb18"),
    ("Trump-backed Bernie Moreno wins Ohio GOP Senate primary, but ...",
     AP + "republicans-ohio-moreno-trump-sherrod-senate-da843cbb08b9233a180081cde6676a5f"),
    ("Republican Tim Sheehy defeats Jon Tester to win Montana US ...",                   # truncated: office unknown
     AP + "senate-election-tester-sheehy-montana-f882b50bf4af6a87ec32e3a5f626eccb"),
    ("Democrat Ruben Gallego leads Republican Kari Lake in US ...",                      # leads, not wins
     AP + "arizona-senate-election-ruben-gallego-kari-lake-5bd18699aeb3b5e4d761b5af54593ec7"),
    ("Democrat Jacky Rosen reelected to U.S. Senate from Nevada | AP News",              # no "wins": not taken
     AP + "nevada-senate-election-race-2024-f6646cfc6bdfb00d78897322cd25ae44"),
    ("Trump-backed Moreno defeats incumbent US Sen. Sherrod Brown ...",                  # no "wins" / "to win"
     AP + "election-2024-senate-ohio-brown-moreno-74c4b91e5866215d4201377fefcadad0"),
    ("2024 Election highlights: Republicans win Senate majority",                        # live blog
     "https://apnews.com/live/senate-house-election-updates-11-5-2024"),
    ("How the AP calls elections and why it matters | AP News", "https://apnews.com/ap-race-calls-faq"),
]


@pytest.mark.parametrize("title,url,want", AP_2024_POSITIVE)
def test_ap_2024_headlines_match(r24, title, url, want):
    m, why = K.match_ap_headline(title, url, r24)
    assert m is not None, why
    assert (m.state, m.key) == want


@pytest.mark.parametrize("title,url", AP_2024_NEGATIVE)
def test_ap_2024_non_calls_rejected(r24, title, url):
    m, why = K.match_ap_headline(title, url, r24)
    assert m is None, (m, why)


def slug(who: str, state: str) -> str:
    return AP + f"race-call-{who}-wins-{state}-senate-{'ab' * 16}"


AP_2026_POSITIVE = [
    ("AP Race Call: Republican Ken Paxton wins election to U.S. Senate in Texas, beating James Talarico",
     slug("paxton", "texas"), ("TX", "paxton")),
    ("AP Race Call: Democrat James Talarico wins election to U.S ...", slug("talarico", "texas"), ("TX", "talarico")),
    ("AP Race Call: Republican Dan Sullivan wins reelection to U.S. Senate in Alaska", slug("sullivan", "alaska"),
     ("AK", "sullivan")),
    ("AP Race Call: Democrat Mary Peltola wins election to U.S. Senate in Alaska", slug("peltola", "alaska"), ("AK", "peltola")),
    ("AP Race Call: Republican Roger Marshall wins reelection to U.S. Senate in Kansas", slug("marshall", "kansas"),
     ("KS", "marshall")),
    ("AP Race Call: Republican Susan Collins wins reelection to U.S. Senate in Maine", slug("collins", "maine"), ("ME", "collins")),
    ("AP Race Call: Democrat Troy Jackson wins election to U.S ...", slug("jackson", "maine"), ("ME", "jackson")),
    ("AP Race Call: Democrat Sherrod Brown wins special election to U.S. Senate in Ohio", slug("brown", "ohio"), ("OH", "brown")),
    ("AP Race Call: Republican Jon Husted wins special election to U.S ...", slug("husted", "ohio"), ("OH", "husted")),
    ("AP Race Call: Democrat Abdul El-Sayed wins election to U.S. Senate in Michigan", slug("el-sayed", "michigan"),
     ("MI", "elsayed")),
    ("AP Race Call: Republican Mike Rogers wins election to U.S. Senate in Michigan", slug("rogers", "michigan"), ("MI", "rogers")),
    ("AP Race Call: Republican Shelley Moore Capito wins reelection to U.S. Senate in West Virginia",
     slug("capito", "west-virginia"), ("WV", "capito")),
    ("AP Race Call: Republican Tom Cotton wins reelection to U.S. Senate in Arkansas", slug("cotton", "arkansas"), ("AR", "cotton")),
    ("AP Race Call: Republican Cindy Hyde-Smith wins reelection to U.S. Senate in Mississippi", slug("hyde-smith", "mississippi"),
     ("MS", "hydesmith")),
    ("AP Race Call: Independent Dan Osborn wins election to U.S. Senate in Nebraska", slug("osborn", "nebraska"), ("NE", "osborn")),
    ("AP Race Call: Democrat Cory Booker wins reelection to U.S. Senate in New Jersey", slug("booker", "new-jersey"),
     ("NJ", "booker")),
    ("AP Race Call: Democrat Ben Ray Luján wins reelection to U.S. Senate in New Mexico", slug("lujan", "new-mexico"),
     ("NM", "lujan")),
    ("Republican Ken Paxton wins Texas Senate race, defeating Democrat James Talarico", AP + "texas-senate-paxton-" + "c" * 32,
     ("TX", "paxton")),
]


@pytest.mark.parametrize("title,url,want", AP_2026_POSITIVE)
def test_ap_2026_headlines_match(title, url, want):
    m, why = K.match_ap_headline(title, url, R26)
    assert m is not None, why
    assert (m.state, m.key) == want


AP_2026_NEGATIVE = [
    ("Paxton wins Senate primary runoff, defeats Cornyn | AP News", "https://apnews.com/live/election-primary-texas-runoff-05-26-2026"),
    ("Paxton wins Senate primary runoff, defeats Cornyn", AP + "texas-runoff-" + "d" * 32),
    ("AP Race Call: Ken Paxton wins Republican nomination for U.S. Senate in Texas", slug("paxton", "texas")),
    ("AP Race Call: Ken Paxton wins Republican primary runoff for U.S. Senate in Texas", slug("paxton", "texas")),
    ("James Talarico wins Texas Democratic Senate nomination", AP + "talarico-" + "e" * 32),
    ("Abdul El-Sayed wins Michigan Democratic Senate primary", AP + "elsayed-" + "e" * 32),
    ("Opinion: Why Talarico wins the Texas Senate race", AP + "opinion-talarico-" + "f" * 32),
    ("How Ken Paxton wins the Texas Senate race", AP + "paxton-" + "f" * 32),
    ("Can Sherrod Brown win back Ohio's Senate seat?", AP + "brown-" + "f" * 32),
    ("If Collins wins the Maine Senate race, Republicans keep control", AP + "collins-" + "f" * 32),
    ("Peltola wins endorsement in Alaska Senate race", AP + "peltola-" + "f" * 32),
    ("Husted wins debate in Ohio Senate race, voters say", AP + "husted-" + "f" * 32),
    ("Paxton expected to win Texas Senate race, poll finds", AP + "paxton-poll-" + "f" * 32),
    ("AP Race Call: Republican Mike Rogers wins election for governor in Michigan", slug("rogers", "michigan")),
    ("AP Race Call: Republican Jon Husted wins election to Ohio state Senate", slug("husted", "ohio")),
    ("AP Race Call: Democrat Ken Paxton wins election to U.S. Senate in Texas", slug("paxton", "texas")),       # wrong party
    ("AP Race Call: Republican Ken Paxton wins election to U.S. Senate in Texas", slug("paxton", "kansas")),   # URL disagrees
    ("AP Race Call: Republican Ken Paxton wins election to U.S. Senate in Texas", slug("talarico", "texas")),  # URL disagrees
    ("AP Race Call: Republican John Cornyn wins reelection to U.S. Senate in Texas", slug("cornyn", "texas")),  # not on the ballot
    ("Sullivan wins Alaska Senate race", AP + "alaska-sullivan-" + "a" * 32),                                    # two Sullivans
    ("AP Race Call: Ken Paxton wins election to U.S. Senate in Kansas", slug("paxton", "kansas")),             # not in KS race
    ("Paxton and Talarico make final pitch as Texas Senate race nears end", AP + "texas-" + "b" * 32),
    ("Midterm elections live updates: Paxton wins Texas Senate race", "https://apnews.com/live/midterm-election-2026"),
    ("2026 Midterm Election Results: Senate, House and Governor Races", "https://apnews.com/projects/elections-2026/us-senate-results/"),
]


@pytest.mark.parametrize("title,url", AP_2026_NEGATIVE)
def test_ap_2026_non_calls_rejected(title, url):
    m, why = K.match_ap_headline(title, url, R26)
    assert m is None, (m, why)


def test_alaska_sullivans_are_told_apart():
    m, _ = K.match_ap_headline("AP Race Call: Daniel J. Sullivan Jr. wins election to U.S. Senate in Alaska",
                               slug("sullivan", "alaska"), R26)
    assert m and m.key == "sullivan_j"
    m, _ = K.match_ap_headline("Republican Dan Sullivan wins Alaska Senate race", AP + "x-" + "a" * 32, R26)
    assert m and m.key == "sullivan"


# ---------------------------------------------------------------- other outlets: explicit AP attribution

def test_outlets_attributing_the_call_to_ap(r24):
    m, why = K.match_attributed(
        "AP calls race for Republican Dave McCormick; Casey not yet ...",
        "Nov 7, 2024 · It took two days, but the Associated Press has called the Pa. Senate race for Republican Dave "
        "McCormick. It's been a razor-close race. The Casey campaign still isn't conceding though.", r24)
    assert m and (m.state, m.key) == ("PA", "mccormick"), why
    m, why = K.match_attributed("AP calls Pennsylvania's U.S. Senate race for Dave McCormick ...",
                                "Nov 7, 2024 · Democrats criticized the AP on Thursday for calling the race", r24)
    assert m and (m.state, m.key) == ("PA", "mccormick"), why
    m, why = K.match_attributed("Why AP called the Michigan Senate race for Elissa Slotkin",
                                "Nov 6, 2024 · WASHINGTON (AP) — Democratic Rep. Elissa Slotkin won Michigan’s razor’s-edge "
                                "race for U.S. Senate, defeating former Republican congressman Mike Rogers.", r24)
    assert m and (m.state, m.key) == ("MI", "slotkin"), why
    m, why = K.match_attributed("Slotkin wins in Michigan",
                                "Democrat Elissa Slotkin has won an open U.S. Senate seat in Michigan. The Associated Press "
                                "called the race Wednesday.", r24)
    assert m and (m.state, m.key) == ("MI", "slotkin"), why
    m, why = K.match_attributed("Marshall wins Kansas Senate race, AP projects", "", R26)
    assert m and (m.state, m.key) == ("KS", "marshall"), why
    m, why = K.match_attributed("Election night", "The Associated Press declared Ken Paxton the winner of the Texas "
                                                   "Senate race at 10:42 p.m.", R26)
    assert m and (m.state, m.key) == ("TX", "paxton"), why


@pytest.mark.parametrize("title,content", [
    ("Democrats disagree with AP calling victory for McCormick",
     "Nov 8, 2024 · Dave McCormick was leading longtime incumbent Sen. Bob Casey by over 30,000 votes"),
    ("Illinois Senate forecast 2026: Juliana Stratton vs Don Tracy ...",
     "3 days ago · Democrat Juliana Stratton has a more than 99% chance to win the 2026 Illinois Senate race against Don Tracy"),
    ("Texas Senate race too close to call", "The Associated Press has not called the Texas Senate race for Paxton or Talarico."),
    ("Paxton leads in Texas", "AP has yet to call the Texas Senate race for Ken Paxton."),
    ("Ohio Senate: Husted declares victory", "Husted declared victory before the AP called the race."),
    ("How the AP calls elections | WBUR News", "1 day ago · The Associated Press will declare winners in more than 5,200 races"),
    ("Decision Desk HQ calls Texas Senate race for Paxton", "Decision Desk HQ projects Ken Paxton wins the Texas Senate race."),
    ("NBC News projects Brown wins Ohio Senate race", "NBC News projects Sherrod Brown will win the Ohio Senate race."),
    ("AP calls Ohio governor race for Ramaswamy", "The Associated Press called the Ohio governor's race for Vivek Ramaswamy."),
    ("AP calls Texas Senate primary runoff for Paxton", "The Associated Press called the Texas Senate primary runoff for Ken Paxton."),
])
def test_outlets_non_calls_rejected(title, content):
    m, why = K.match_attributed(title, content, R26)
    assert m is None, (m, why)


def test_syndicated_truncated_title_uses_the_lede(r24):
    hit = {"url": "https://wreg.com/news/your-voice-your-vote/ap-politics/ap-ap-race-call-democrat-ruben-gallego-wins-election-to",
           "title": "AP Race Call: Democrat Ruben Gallego wins election …",
           "content": "Democrat Ruben Gallego won the Arizona Senate race on Monday, returning the seat to the Democratic "
                      "column two years after retiring independent Sen. Kyrsten Sinema left the party. He defeated ..."}
    close = {st: dt.datetime(2024, 11, 6, tzinfo=dt.timezone.utc) for st in r24}
    m, why = K.match_hit(hit, r24, close)
    assert m and (m.state, m.key, m.matched_by) == ("AZ", "gallego", "ap_syndicated"), why


# ---------------------------------------------------------------- dates

def test_old_stories_are_rejected_by_date():
    hit = {"url": slug("collins", "maine"), "title": "AP Race Call: Republican Susan Collins wins reelection to U.S. Senate in Maine",
           "content": "Nov 4, 2020 · Republican Sen. Susan Collins won reelection ...", "publishedDate": None}
    assert K.match_hit(hit, R26, CLOSE26)[0] is None
    hit.update(content="", publishedDate="2026-11-03T13:00:00")              # before polls closed
    assert K.match_hit(hit, R26, CLOSE26)[0] is None
    hit.update(content="6 days ago · Collins ...", publishedDate=None)
    assert K.match_hit(hit, R26, CLOSE26)[0] is None
    hit.update(content="", publishedDate="2026-11-04T02:31:00")              # after ME's 8 pm ET close
    assert K.match_hit(hit, R26, CLOSE26)[0].key == "collins"
    hit.update(content="35 minutes ago · Collins ...", publishedDate=None)  # rough relative times are not judged
    assert K.match_hit(hit, R26, CLOSE26)[0].key == "collins"


# ---------------------------------------------------------------- monitor: writes candidates only

@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "CALLS", tmp_path / "calls.json")
    monkeypatch.setattr(K, "CANDIDATES", tmp_path / "call_candidates.json")
    return tmp_path


def fake_search(results):
    def search(query, time_range=None):
        return [dict(r) for r in results], True
    return search


def test_monitor_baseline_then_night(files):
    old = {"url": slug("collins", "maine").replace("ab" * 16, "cd" * 16),
           "title": "AP Race Call: Republican Susan Collins wins reelection to U.S. Senate in Maine", "content": "", "publishedDate": None}
    pre = dt.datetime(2026, 11, 3, 20, 0, tzinfo=dt.timezone.utc)
    out = K.run_cycle(0, R26, CLOSE26, search=fake_search([old]), now=pre, baseline=True, gap_s=0)
    assert out["candidates"] == [] and old["url"] in out["pre_close_urls"]
    new = {"url": slug("paxton", "texas"), "title": "AP Race Call: Republican Ken Paxton wins election to U.S. Senate in Texas",
           "content": "", "publishedDate": "2026-11-04T03:42:00"}
    rival = {"url": slug("talarico", "texas").replace("ab" * 16, "ef" * 16),
             "title": "AP Race Call: Democrat James Talarico wins election to U.S ...", "content": "", "publishedDate": None}
    retraction = {"url": "https://example.com/ap-retracts", "title": "AP retracts its call in the Texas Senate race",
                  "content": "", "publishedDate": None}
    night = dt.datetime(2026, 11, 4, 3, 50, tzinfo=dt.timezone.utc)
    out = K.run_cycle(1, R26, CLOSE26, search=fake_search([old, new, rival, retraction]), now=night, gap_s=0)
    got = {(c["state"], c["key"]) for c in out["candidates"]}
    assert got == {("TX", "paxton"), ("TX", "talarico")}             # the old Maine story stays ignored
    assert out["conflicts"] == {"TX": ["paxton", "talarico"]}
    assert out["alerts"] and out["alerts"][0]["states"] == ["TX"]
    tal = next(c for c in out["candidates"] if c["key"] == "talarico")
    assert tal["warnings"] and tal["published"] is None and tal["outlet"] == "apnews.com"
    assert not (files / "calls.json").exists()                       # the monitor never writes calls
    assert json.loads((files / "call_candidates.json").read_text())["candidates"]


def test_monitor_skips_states_whose_polls_are_open(files):
    early = dt.datetime(2026, 11, 3, 23, 0, tzinfo=dt.timezone.utc)
    qs = K.queries_for_cycle(0, R26, CLOSE26, set(), early)
    assert [s for _, _, s in qs if s] == []                           # nothing has closed at 6 pm ET
    late = dt.datetime(2026, 11, 4, 2, 5, tzinfo=dt.timezone.utc)
    qs = K.queries_for_cycle(0, R26, CLOSE26, {"OH"}, late)
    states = [s for _, _, s in qs if s]
    assert states[:4] == ["TX", "KS", "ME", "MI"] and "OH" not in states and "AK" not in states
    assert len(states) == 4 + K.OTHERS_PER_CYCLE


# ---------------------------------------------------------------- confirm / retract

NIGHT = dt.datetime(2026, 11, 4, 4, 0, tzinfo=dt.timezone.utc)


def test_confirm_retract_list(files, capsys):
    url = slug("paxton", "texas")
    e = K.confirm("TX", "paxton", url, "apnews.com", "10:42 PM ET", "tester", now=NIGHT)
    assert e["name"] == "Ken Paxton" and e["party"] == "REP"
    doc = json.loads((files / "calls.json").read_text())
    assert doc["calls"]["TX"]["key"] == "paxton" and K.confirmed_calls().keys() == {"TX"}
    K.confirm("TX", "paxton", url, "apnews.com", "10:43 PM ET", "tester", now=NIGHT)          # same call: update
    with pytest.raises(SystemExit, match="already confirmed"):
        K.confirm("TX", "talarico", url, "apnews.com", "10:50 PM ET", "tester", now=NIGHT)
    K.retract("TX", "AP retracted its call", "tester", now=NIGHT)
    assert K.confirmed_calls() == {}
    doc = json.loads((files / "calls.json").read_text())
    assert doc["calls"]["TX"]["retracted"] is True and [h["action"] for h in doc["history"]] == ["confirm", "confirm", "retract"]
    with pytest.raises(SystemExit, match="no confirmed call"):
        K.retract("TX", "again", "tester", now=NIGHT)
    K.confirm("TX", "talarico", slug("talarico", "texas"), "apnews.com", "11:05 PM ET", "tester", now=NIGHT)
    assert K.confirmed_calls()["TX"]["key"] == "talarico"
    K.show()
    assert "TX talarico" in capsys.readouterr().out


@pytest.mark.parametrize("args,msg", [
    (("TX", "cornyn", "https://apnews.com/article/x", "apnews.com", "10:42 PM ET"), "unknown candidate"),
    (("ZZ", "paxton", "https://apnews.com/article/x", "apnews.com", "10:42 PM ET"), "no 2026 Senate race"),
    (("TX", "paxton", "http://apnews.com/article/x", "apnews.com", "10:42 PM ET"), "https"),
    (("TX", "paxton", "https://www.npr.org/2026/11/04/x", "apnews.com", "10:42 PM ET"), "not the story's site"),
    (("TX", "paxton", "https://apnews.com/article/x", "apnews.com", "22:42"), "10:42 PM ET"),
])
def test_confirm_validation(files, args, msg):
    with pytest.raises(SystemExit, match=msg):
        K.confirm(*args, by="tester", now=NIGHT)
    assert not (files / "calls.json").exists()


def test_confirm_refused_before_polls_close(files):
    with pytest.raises(SystemExit, match="polls have not all closed"):
        K.confirm("AK", "sullivan", slug("sullivan", "alaska"), "apnews.com", "11:30 PM ET", "tester", now=NIGHT)  # AK: 1 am ET
    K.confirm("TX", "paxton", "https://www.npr.org/2026/11/04/texas-senate", "npr.org", "10:42 PM ET", "tester", now=NIGHT)

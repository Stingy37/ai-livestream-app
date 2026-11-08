"""AP race-call candidates for the 35 Senate races, and the operator-confirmed calls file.

Legal rules 2-7 (research/election/legal.md): a winner is named only as an AP declaration taken from a published news
report, and is removed at once if AP retracts it. So this module has two halves that never mix:

* ``monitor`` searches the local SearXNG (src/scraper/searx.py; start it with scripts/searxng_start.sh) every ~5 min for
  AP race-call stories and writes CANDIDATES (output/election/call_candidates.json). It NEVER writes the calls file.
  It reads search-result titles, URLs and snippets only; it never fetches AP pages (rule 6).
* ``confirm`` / ``retract`` are run by a human who has read the story. Only they write CALLS
  (output/election/calls.json), the file src/election/snapshot.py reads.

    cd src
    python -m election.calls baseline                  # once, before polls close: old stories are ignored later
    python -m election.calls monitor [--once] [--interval 300]
    python -m election.calls confirm TX paxton --url https://apnews.com/article/... --outlet apnews.com --at "10:42 PM ET"
    python -m election.calls retract TX --reason "AP retracted its call"
    python -m election.calls list

What counts as a candidate (``match_hit``):
* apnews.com: a headline that says the candidate WINS the U.S. Senate race in that state, e.g. AP's own format
  "AP Race Call: Republican Dave McCormick wins election to U.S. Senate in Pennsylvania" (URL
  /article/race-call-mccormick-wins-pennsylvania-senate-<hash>), or "Why AP called the <State> Senate race for <X>".
  Search titles are often truncated ("... wins election to U.S ..."); the race-call URL slug then supplies the state
  and office, and must agree with the title where both say something.
* any other outlet: an explicit attribution to AP ("AP calls Pennsylvania's U.S. Senate race for Dave McCormick",
  "The Associated Press declared X the winner", a syndicated "AP Race Call: ..." story).
* never: primaries, nominations, runoffs, governor / House / state-senate races, opinion, forecasts, questions,
  conditionals, live blogs, stories dated before election day, or names that are not on the state's 2026 ballot.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("election.calls")

REPO = Path(__file__).resolve().parents[2]
RACES = Path(os.environ.get("ELECTION_RACES", REPO / "data" / "election" / "races.json"))
CALLS = Path(os.environ.get("ELECTION_CALLS", REPO / "output" / "election" / "calls.json"))
CANDIDATES = Path(os.environ.get("ELECTION_CALL_CANDIDATES", REPO / "output" / "election" / "call_candidates.json"))
RUN_DIR = REPO / ".run" / "election"
STOP_FILE = REPO / ".run" / "STOP_ELECTION_CALLS"
ELECTION_DAY = dt.date(2026, 11, 3)
QUERY_GAP_S = float(os.environ.get("ELECTION_CALLS_QUERY_GAP_S", "6"))
OTHERS_PER_CYCLE = int(os.environ.get("ELECTION_CALLS_OTHERS_PER_CYCLE", "4"))   # keep the search engines' load low
FEATURED = ("TX", "AK", "KS", "ME", "OH", "MI")
UTC = dt.timezone.utc

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
# AP-style abbreviations used in news copy ("the Pa. Senate race"); matched case-sensitively with the period
AP_ABBR = {"AL": "Ala.", "AZ": "Ariz.", "AR": "Ark.", "CA": "Calif.", "CO": "Colo.", "DE": "Del.", "FL": "Fla.",
           "GA": "Ga.", "IL": "Ill.", "IN": "Ind.", "KS": "Kan.", "KY": "Ky.", "LA": "La.", "MD": "Md.", "MA": "Mass.",
           "MI": "Mich.", "MN": "Minn.", "MS": "Miss.", "MT": "Mont.", "NE": "Neb.", "NV": "Nev.", "NH": "N.H.",
           "NJ": "N.J.", "NM": "N.M.", "NC": "N.C.", "OK": "Okla.", "OR": "Ore.", "PA": "Pa.", "RI": "R.I.",
           "SC": "S.C.", "SD": "S.D.", "TN": "Tenn.", "VA": "Va.", "WV": "W.Va.", "WY": "Wyo."}
PARTY_WORDS = {"republican": "REP", "gop": "REP", "democrat": "DEM", "democratic": "DEM", "independent": "IND",
               "libertarian": "LIB", "green": "GRN"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

# a headline with any of these is not a general-election U.S. Senate race call (checked on the normalised text)
NEGATIVE = re.compile(
    r"\b(primary|primaries|nominat\w*|nominee\w*|runoff\w*|run off|caucus\w*|convention|governor\w*|gubernatorial|"
    r"house|congressional|district|state senate|legislat\w*|mayor\w*|attorney general|secretary of state|lieutenant|"
    r"opinion|analysis|commentary|editorial|column|letters?|poll|polls|polling|forecast\w*|odds|chances?|predict\w*|"
    r"projected|projection|expected|favou?red|likely|could|would|might|can|will|if|how|what|whether|should|"
    r"endorse\w*|debate\w*|fundrais\w*|ads?|lawsuit|court|recount|live|updates|takeaways|explainer|quiz|"
    r"preview|guide|watch)\b")
# prose (snippets, ledes) gets narrower lists: another office or a primary, and speculation
NEG_RACE = re.compile(r"\b(primary|primaries|nominat\w*|nominee\w*|runoff\w*|run off|caucus\w*|convention|governor\w*|"
                      r"gubernatorial|house|congressional|district|state senate|legislat\w*|mayor\w*|attorney general|"
                      r"secretary of state|lieutenant)\b")
NEG_SPECULATIVE = re.compile(r"\b(opinion|analysis|commentary|editorial|poll|polls|polling|forecast\w*|odds|chances?|"
                             r"predict\w*|projected (margin|to)|expected|favou?red|likely|could|would|might|if|whether)\b")
NEGATED_CALL = re.compile(r"\b(not|n t|yet to|too close|too early|before|until|when|if|whether|no|without|disagree\w*|"
                          r"critici\w*|retract\w*|rescind\w*|withdr[ae]w\w*)\b")
RETRACTION = re.compile(r"\b(ap|associated press)\b[^.;]{0,60}\b(retract\w*|rescind\w*|withdr[ae]w\w*|uncall\w*|"
                        r"revers\w*)\b[^.;]{0,40}\bcall|\bcall\w*\b[^.;]{0,40}\b(retracted|rescinded|withdrawn)\b")
RACE_CALL_SLUG = re.compile(r"^/article/(?:ap-)?race-call-(?P<who>[a-z0-9-]+?)-wins-(?P<rest>[a-z0-9-]+?)-"
                            r"(?P<hash>[0-9a-f]{32})/?$")


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- text normalisation

def norm(s: str) -> str:
    """Lowercase ASCII, curly quotes straightened, "U.S." -> "us", "Sen." -> "sen", whitespace collapsed."""
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("…", "...")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\bu\.\s?s\.?(?=\s|$|[^a-z])", "us", s)
    s = re.sub(r"\b(sen|rep|gov|jr|sr|st|dr|mr|ms|mrs|a\.m|p\.m)\.", lambda m: m.group(1).replace(".", ""), s)
    s = s.replace("'", " ")
    return re.sub(r"\s+", " ", s).strip()


def flat(s: str) -> str:
    """norm() with hyphens dropped, for names: "El-Sayed" -> "elsayed", "Hyde-Smith" -> "hydesmith"."""
    return re.sub(r"(?<=[a-z])-(?=[a-z])", "", norm(s))


def has_words(text: str, words: str) -> bool:
    return bool(words) and re.search(rf"(?<![a-z0-9]){re.escape(words)}(?![a-z0-9])", text) is not None


# ---------------------------------------------------------------- roster (data/election/races.json)

@dataclass(frozen=True)
class Cand:
    state: str
    key: str
    name: str
    party: str
    first: str
    surname: str       # flat(), possibly several words ("blunt rochester")
    suffix: str


def _cand(state: str, c: dict) -> Cand:
    toks = [t for t in re.split(r"\s+", c["name"].strip()) if t]
    suffix = ""
    if toks and flat(toks[-1]).rstrip(".") in SUFFIXES:
        suffix = flat(toks.pop()).rstrip(".")
    surname = flat(toks[-1]) if toks else flat(c["key"])
    key = re.sub(r"[^a-z]", "", c["key"].split("_")[0])
    for i in range(len(toks) - 1, 0, -1):          # a multi-word surname spelled out by the key: "Fetty Anderson"
        if re.sub(r"[^a-z]", "", flat(" ".join(toks[i:]))) == key:
            surname = flat(" ".join(toks[i:]))
            break
    first = flat(toks[0]).rstrip(".") if len(toks) > 1 else ""
    return Cand(state, c["key"], c["name"], c.get("party", "OTH"), first, surname, suffix)


def load_roster(path: Path = RACES) -> tuple[dict[str, list[Cand]], dict[str, dt.datetime]]:
    """({state: [Cand]}, {state: last poll close}) for the 2026 Senate races."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    roster: dict[str, list[Cand]] = {}
    close: dict[str, dt.datetime] = {}
    for r in d["senate_races"]:
        st = r["state"]
        seen, out = set(), []
        people = r.get("nominees", []) + (r.get("other_candidates") or [])
        people += (d.get("featured", {}).get(st, {}) or {}).get("candidates", [])
        for c in people:
            if c.get("key") and c["key"] not in seen:
                seen.add(c["key"])
                out.append(_cand(st, c))
        roster[st] = out
        times = [dt.datetime.fromisoformat(r[k]) for k in ("poll_close_et", "poll_close_et_main") if r.get(k)]
        close[st] = max(times) if times else dt.datetime(2026, 11, 4, 6, tzinfo=UTC)
    return roster, close


def states_in(text_original: str, only: set[str] | None = None) -> set[str]:
    """States named in a headline/snippet: full names (longest first, so West Virginia is not Virginia) and AP
    abbreviations ("Pa."); with ``only``, states outside it (no 2026 Senate race) are ignored."""
    t = norm(text_original)
    found = set()
    for st, name in sorted(STATE_NAMES.items(), key=lambda kv: -len(kv[1])):
        n = name.lower()
        if has_words(t, n):
            found.add(st)
            t = re.sub(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", " ", t)
    for st, ab in AP_ABBR.items():
        if re.search(rf"(?<![A-Za-z.]){re.escape(ab)}", text_original or ""):
            found.add(st)
    return found & only if only is not None else found


def state_from_slug(slug_rest: str) -> str | None:
    """'pennsylvania-senate' -> PA; 'new-hampshire-governor' -> NH (the office is checked by the caller)."""
    for st, name in sorted(STATE_NAMES.items(), key=lambda kv: -len(kv[1])):
        s = name.lower().replace(" ", "-")
        if slug_rest == s or slug_rest.startswith(s + "-"):
            return st
    return None


def pick_candidate(subject: str, cands: list[Cand]) -> tuple[Cand | None, str]:
    """The one candidate the subject phrase names (surname as whole words; first name / suffix break ties)."""
    f = flat(subject)
    hits = [c for c in cands if has_words(f, c.surname)]
    if not hits:
        return None, "no 2026 candidate of the state is named"
    if len(hits) > 1:        # same surname (Alaska: Dan Sullivan, Daniel J. Sullivan Jr.): the first name or suffix must say
        scored = []
        for c in hits:
            score = 2 if c.first and re.search(rf"(?<![a-z]){re.escape(c.first)}( [a-z]\.?)? {re.escape(c.surname)}(?![a-z])", f) else 0
            score += 2 if c.suffix and has_words(f, c.suffix) else (-2 if not c.suffix and re.search(r"\b(jr|sr|ii|iii)\b", f) else 0)
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        if scored[0][0] < 2 or scored[0][0] == scored[1][0]:
            return None, f"ambiguous between {[c.key for _, c in scored]}"
        return scored[0][1], ""
    return hits[0], ""


def party_conflict(subject: str, cand: Cand) -> bool:
    words = [PARTY_WORDS[w] for w in re.findall(r"[a-z]+", norm(subject)) if w in PARTY_WORDS]
    return bool(words) and cand.party not in words


# ---------------------------------------------------------------- the matcher

@dataclass
class Match:
    state: str
    key: str
    name: str
    party: str
    matched_by: str          # ap_headline | ap_explainer | ap_syndicated | ap_attributed
    evidence: str


def _strip_title(title: str) -> tuple[str, bool]:
    """Drop the site suffix (" | AP News") and note whether the search engine truncated the title."""
    t = re.sub(r"\s*[|\-–]\s*(AP News|The Associated Press|Associated Press)\s*$", "", (title or "").strip())
    truncated = bool(re.search(r"(\.\.\.|…)\s*$", t))
    return re.sub(r"\s*(\.\.\.|…)\s*$", "", t).strip(), truncated


def match_ap_headline(title: str, url: str, roster: dict[str, list[Cand]], form: str = "ap_headline") -> tuple[Match | None, str]:
    """An apnews.com (or syndicated "AP Race Call:") headline saying a 2026 candidate wins that state's Senate race."""
    t, truncated = _strip_title(title)
    n = norm(t)
    path = urlsplit(url).path if url else ""
    slug = RACE_CALL_SLUG.match(path) if "apnews.com" in (urlsplit(url).hostname or "") else None
    if "/live/" in path:
        return None, "live blog (title changes during the night)"
    if "/opinion/" in path or "/hub/" in path or "/projects/" in path:
        return None, "not a news story"
    m = re.match(r"^why (the )?ap called (the )?(?P<race>.+?) senate (race|seat|contest|election) for (?P<who>.+)$", n)
    if m:
        neg = NEGATIVE.search(re.sub(r"^why ", "", n))
        if neg and neg.group(0) not in ("how", "what"):
            return None, f"excluded word {neg.group(0)!r}"
        sts = states_in(m.group("race"), set(roster))
        if len(sts) != 1:
            return None, f"state not clear ({sorted(sts)})"
        st = sts.pop()
        cand, why = pick_candidate(m.group("who"), roster.get(st, []))
        if not cand or party_conflict(m.group("who"), cand):
            return None, why or "party word does not match the candidate"
        return Match(st, cand.key, cand.name, cand.party, "ap_explainer", t), ""
    body = re.sub(r"^ap race call:\s*", "", n)
    neg = NEGATIVE.search(body)
    if neg:
        return None, f"excluded word {neg.group(0)!r}"
    if "?" in body:
        return None, "a question"
    v = re.search(r"\b(wins|defeats|beats|ousts|tops)\b", body)
    if not v:
        return None, "no 'wins'"
    if v.group(1) != "wins" and not re.search(r"\bto win\b", body[v.end():]):
        return None, "no 'wins' / 'to win'"
    subject, predicate = body[:v.start()].strip(" ,:"), body[v.start():]
    if not subject or len(subject.split()) > 8:
        return None, "no short subject before the verb"
    if slug:
        rest = slug.group("rest")
        st_slug = state_from_slug(rest)
        office = rest[len(STATE_NAMES[st_slug].replace(" ", "-")):].strip("-") if st_slug else ""
        if not st_slug or not office.startswith("senate"):
            return None, f"race-call URL is not a Senate race ({rest!r})"
    else:
        st_slug = None
    if not has_words(predicate, "senate"):
        if not (truncated and st_slug):
            return None, "no 'Senate' after the verb"
    sts = states_in(predicate, set(roster))
    if len(sts) > 1:
        return None, f"several states named ({sorted(sts)})"
    st = next(iter(sts), None)
    if st and st_slug and st != st_slug:
        return None, f"title says {st}, URL says {st_slug}"
    st = st or st_slug
    if not st:
        return None, "no state named"
    if st not in roster:
        return None, f"{st} has no 2026 Senate race"
    cand, why = pick_candidate(subject, roster[st])
    if cand and slug and not has_words(flat(slug.group("who").replace("-", " ")), cand.surname.replace("-", " ")) \
            and flat(slug.group("who").replace("-", "")) != cand.surname.replace(" ", ""):
        return None, f"URL names {slug.group('who')!r}, title names {cand.key!r}"
    if not cand:
        return None, why
    if party_conflict(subject, cand):
        return None, "party word does not match the candidate"
    return Match(st, cand.key, cand.name, cand.party, form, t), ""


def _sentences(text: str) -> list[str]:
    t = (text or "").replace("…", ". ")
    t = re.sub(r"\b(U\.S|Sen|Rep|Gov|Jr|Sr|St|Dr|Mr|Ms|Mrs|a\.m|p\.m)\.", lambda m: m.group(1).replace(".", "") + "", t)
    for ab in AP_ABBR.values():                     # keep "Pa." inside its sentence
        t = t.replace(ab + " ", ab.replace(".", "․") + " ")
    return [s.replace("․", ".").strip() for s in re.split(r"(?<=[.!?;])\s+", t) if s.strip()]


def match_attributed(title: str, content: str, roster: dict[str, list[Cand]]) -> tuple[Match | None, str]:
    """Another outlet's (or a snippet's) explicit attribution of the call to AP."""
    content = re.sub(r"^\s*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d+ \w+ ago)\s*[·\-—]\s*", "", content or "")   # date
    content = re.sub(r"^\s*[A-Z][A-Z .,'-]{2,40}\s*\((AP|Reuters)\)\s*[—–-]+\s*", "", content)      # WASHINGTON (AP) —
    sents = _sentences(title) + _sentences(content)
    only = set(roster)
    for i, s in enumerate(sents):
        n = norm(s)
        if not re.search(r"\b(ap|associated press)\b", n):
            continue
        sts = states_in(s, only)
        who = None
        m = re.search(r"\b(ap|associated press)\b (has )?(called|calls|declared|declares) (the )?(?P<race>[^;]{0,60}?)"
                      r"\b(race|seat|contest)s? for (?P<who>[^;,]{2,60})", n)
        if m and has_words(m.group("race") + " ", "senate") or (m and not m.group("race").strip()):
            who, pre = m.group("who"), n[:m.start()] + " " + m.group("race")
        if who is None:
            m = re.search(r"\b(ap|associated press)\b (has )?(declared|declares) (?P<who>[^;,]{2,60}?) (the )?winner", n)
            if m:
                who, pre = m.group("who"), n[:m.start()]
        if who is None:      # "Marshall wins Kansas Senate race, AP projects" / "..., according to the Associated Press"
            m = re.search(r"^(?P<who>[^,;]{2,60}?) (wins|has won|won) (?P<race>[^;]{0,80}?\bsenate\b[^;]{0,60}?),? "
                          r"(according to |per |the )?(the )?(ap|associated press)( (projects|says|reports|declares|calls|"
                          r"declared|called|projected))?\b", n)
            if m:
                who, pre = m.group("who"), m.group("race")
        if who is None:      # "X has won ... Senate seat in Michigan. The Associated Press called/declared the race ..."
            if re.search(r"\b(ap|associated press)\b (has )?(called|declared) the race\b", n) and i > 0:
                prev = norm(sents[i - 1])
                m = re.match(r"^(?P<who>[^,;]{2,60}?) (has won|won|wins)\b(?P<rest>.*)$", prev)
                if m and has_words(m.group("rest"), "senate"):
                    who, pre, sts = m.group("who"), m.group("rest"), states_in(sents[i - 1], only) | sts
        if who is None:
            continue
        hit = NEGATED_CALL.search(pre) or NEG_RACE.search(n) or NEG_SPECULATIVE.search(n)
        if hit:
            return None, f"negated or excluded ({hit.group(0)!r})"
        if not has_words(n, "senate") and not (i > 0 and has_words(norm(sents[i - 1]), "senate")):
            # the title "AP calls race for Republican Dave McCormick" says no office: the snippet must
            if not any(has_words(norm(x), "senate") for x in sents):
                return None, "no 'Senate'"
            sts = sts or set().union(*(states_in(x, only) for x in sents))
        if len(sts) != 1:
            return None, f"state not clear ({sorted(sts)})"
        st = sts.pop()
        cand, why = pick_candidate(who, roster.get(st, []))
        if not cand:
            return None, why
        if party_conflict(who, cand):
            return None, "party word does not match the candidate"
        return Match(st, cand.key, cand.name, cand.party, "ap_attributed", s[:300]), ""
    return None, "no explicit AP attribution"


def hit_date(published: str | None, content: str) -> dt.datetime | dt.date | None:
    """The result's date: SearXNG publishedDate, else the engine's "Nov 7, 2024 · ..." / "3 days ago · ..." prefix."""
    if published:
        try:
            t = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
            return t if t.tzinfo else t.replace(tzinfo=UTC)
        except ValueError:
            pass
    m = re.match(r"^\s*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4})\s*[·\-—]", content or "")
    if m:
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%b. %d, %Y"):
            try:
                return dt.datetime.strptime(m.group(1), fmt).date()
            except ValueError:
                continue
    m = re.match(r"^\s*(\d+) (day|week|month|year)s? ago\s*[·\-—]", content or "")
    if m and (m.group(2) != "day" or int(m.group(1)) >= 2):     # engines' "N hours ago" is too rough to judge by
        days = int(m.group(1)) * {"day": 1, "week": 7, "month": 30, "year": 365}[m.group(2)]
        return (now_utc() - dt.timedelta(days=days)).date()
    return None


def too_old(when: dt.datetime | dt.date | None, close: dt.datetime) -> bool:
    """AP never calls before the state's last poll close: anything dated earlier is an old story."""
    if when is None:
        return False
    if isinstance(when, dt.datetime):
        return when < close - dt.timedelta(minutes=30)
    return when < ELECTION_DAY


def outlet_of(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def match_lede(content: str, roster: dict[str, list[Cand]]) -> tuple[str, Cand] | None:
    """The first sentence of a syndicated AP race-call story: "Democrat Ruben Gallego won the Arizona Senate race ..."."""
    content = re.sub(r"^\s*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d+ \w+ ago)\s*[·\-—]\s*", "", content or "")
    content = re.sub(r"^\s*[A-Z][A-Z .,'-]{2,40}\s*\((AP|Reuters)\)\s*[—–-]+\s*", "", content)
    first = next(iter(_sentences(content)), "")
    m = re.match(r"^(?P<who>[^,;]{2,60}?) (has won|won|wins) (?P<rest>[^;]*)$", norm(first))
    if not m or not has_words(m.group("rest"), "senate") or NEG_RACE.search(m.group("rest")):
        return None
    sts = states_in(first, set(roster)) - states_in(m.group("who"), set(roster))
    if len(sts) != 1:
        return None
    st = sts.pop()
    cand, _ = pick_candidate(m.group("who"), roster[st])
    return (st, cand) if cand and not party_conflict(m.group("who"), cand) else None


def match_hit(hit: dict, roster: dict[str, list[Cand]], close: dict[str, dt.datetime]) -> tuple[Match | None, str]:
    """One search result -> a candidate call, or (None, reason). ``hit``: url, title, content, publishedDate."""
    url, title, content = hit.get("url", ""), hit.get("title", ""), hit.get("content", "")
    outlet = outlet_of(url)
    if outlet in ("apnews.com",) or outlet.endswith(".apnews.com"):
        m, why = match_ap_headline(title, url, roster)
    elif norm(title).startswith("ap race call:"):
        m, why = match_ap_headline(title, url, roster, form="ap_syndicated")
        if not m and why in ("no 'Senate' after the verb", "no state named") and _strip_title(title)[1]:
            # a truncated syndicated title ("... wins election …"): the story's lede must name the same person
            lede = match_lede(content, roster)
            subj = re.split(r"\b(wins|defeats|beats|ousts|tops)\b", re.sub(r"^ap race call:\s*", "", norm(title)))[0]
            if lede and pick_candidate(subj, roster[lede[0]])[0] == lede[1] and NEGATIVE.search(norm(title)) is None:
                st, c = lede
                m, why = Match(st, c.key, c.name, c.party, "ap_syndicated", f"{title} / {content[:200]}"), ""
    else:
        m, why = match_attributed(title, content, roster)
    if m and too_old(hit_date(hit.get("publishedDate"), content), close[m.state]):
        return None, "dated before the state's polls closed (an old story)"
    return m, why


# ---------------------------------------------------------------- SearXNG

def searx_search(query: str, time_range: str | None = None) -> tuple[list[dict], bool]:
    import requests
    from scraper.searx import SEARXNG_URL, usable_url
    params = {"q": query, "format": "json", "language": "en", "safesearch": 0}
    if time_range:
        params["time_range"] = time_range
    try:
        r = requests.get(f"{SEARXNG_URL}/search", params=params, timeout=40)
        r.raise_for_status()
        items = r.json().get("results", [])
    except Exception as e:  # noqa: BLE001 - a dead search must not stop the monitor
        log.warning("SearXNG query failed (%r): %s", query, e)
        return [], False
    return [{"url": i.get("url", ""), "title": i.get("title", ""), "content": re.sub(r"\s+", " ", i.get("content") or ""),
             "publishedDate": i.get("publishedDate"), "engine": i.get("engine")}
            for i in items if i.get("url") and usable_url(i["url"])], True


def queries_for_cycle(cycle: int, roster: dict, close: dict, confirmed: set[str], now: dt.datetime,
                      all_states: bool = False) -> list[tuple[str, str | None, str | None]]:
    """[(query, time_range, state or None)]: a few global AP race-call queries, every featured state from 30 min before
    its last poll close (hits before the close are recorded as old stories, so no separate baseline is needed), and
    OTHERS_PER_CYCLE of the other states in rotation (to keep the search engines' load low)."""
    q: list[tuple[str, str | None, str | None]] = [
        ('"AP Race Call" "U.S. Senate"', "day", None),
        ('site:apnews.com "race call" Senate', None, None),
        ('"AP calls" OR "AP declares" OR "Associated Press called" Senate race', "day", None),
    ]
    open_ = [s for s in roster if all_states or now >= close[s] - dt.timedelta(minutes=30)]
    featured = [s for s in FEATURED if s in open_ and s not in confirmed]
    others = [s for s in sorted(open_) if s not in FEATURED and s not in confirmed]
    if not all_states and others:
        k = OTHERS_PER_CYCLE
        start = (cycle * k) % len(others)
        others = (others[start:] + others[:start])[:k]
    for s in featured + others:
        q.append((f'"AP Race Call" {STATE_NAMES[s]} Senate', None if all_states else "day", s))
    return q


# ---------------------------------------------------------------- files

def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class _Lock:
    def __init__(self, path: Path):
        self.path = path.with_name(path.name + ".lock")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def confirmed_calls() -> dict[str, dict]:
    c = _read(CALLS, {}) or {}
    return {k: v for k, v in (c.get("calls") or {}).items() if isinstance(v, dict) and v.get("key") and not v.get("retracted")}


# ---------------------------------------------------------------- monitor

def run_cycle(cycle: int, roster: dict, close: dict, *, search=searx_search, now: dt.datetime | None = None,
              baseline: bool = False, gap_s: float = QUERY_GAP_S) -> dict:
    """One pass of searches; merges into CANDIDATES (never CALLS). Returns the candidates document."""
    if CANDIDATES.resolve() == CALLS.resolve():
        raise RuntimeError("refusing: the candidates file would overwrite the calls file")
    now = now or now_utc()
    doc = _read(CANDIDATES, {}) or {}
    cands: dict[str, dict] = {c["url"]: c for c in doc.get("candidates", []) if c.get("url")}
    pre_close: set[str] = set(doc.get("pre_close_urls", []))
    alerts: dict[str, dict] = {a["url"]: a for a in doc.get("alerts", []) if a.get("url")}
    confirmed = confirmed_calls()
    ok_any, n_q = False, 0
    for query, tr, st_q in queries_for_cycle(cycle, roster, close, set(confirmed), now, all_states=baseline):
        if n_q:
            time.sleep(gap_s)
        n_q += 1
        hits, ok = search(query, tr)
        ok_any |= ok
        for h in hits:
            url = h["url"]
            if url in pre_close:
                continue
            if RETRACTION.search(norm(h.get("title", "") + " " + h.get("content", ""))):
                sts = states_in(h.get("title", "") + " " + h.get("content", ""))
                if not too_old(hit_date(h.get("publishedDate"), h.get("content", "")), now - dt.timedelta(hours=6)):
                    alerts.setdefault(url, {"url": url, "headline": h.get("title", ""), "states": sorted(sts),
                                            "outlet": outlet_of(url), "first_seen": iso(now), "query": query})
            m, why = match_hit(h, roster, close)
            if not m:
                continue
            if baseline or now < close[m.state] - dt.timedelta(minutes=5):
                pre_close.add(url)                 # existed before AP could call this year's race: an old story
                continue
            c = cands.get(url)
            if c is None:
                when = hit_date(h.get("publishedDate"), h.get("content", ""))
                c = cands[url] = {
                    "state": m.state, "key": m.key, "name": m.name, "party": m.party, "url": url,
                    "headline": h.get("title", ""), "published": (iso(when) if isinstance(when, dt.datetime)
                                                                  else when.isoformat() if when else None),
                    "outlet": outlet_of(url), "matched_by": m.matched_by, "evidence": m.evidence,
                    "first_seen": iso(now), "seen": 0, "query": query, "warnings": []}
                if when is None:
                    c["warnings"].append("no date on the search result: check the story's dateline")
                log.info("CANDIDATE %s %s (%s) %s", m.state, m.key, m.matched_by, url)
            c["last_seen"] = iso(now)
            c["seen"] = c.get("seen", 0) + 1
    by_state: dict[str, set[str]] = {}
    for c in cands.values():
        by_state.setdefault(c["state"], set()).add(c["key"])
    conflicts = {st: sorted(keys) for st, keys in by_state.items() if len(keys) > 1}
    disagree = {st: {"confirmed": confirmed[st]["key"], "candidates": sorted(keys)}
                for st, keys in by_state.items() if st in confirmed and keys - {confirmed[st]["key"]}}
    out = {
        "updated_at": iso(now), "cycle": cycle, "searx_ok": ok_any, "queries": n_q,
        "note": "Candidates only. A human confirms with `python -m election.calls confirm ST key --url ... --outlet ... "
                "--at ...`; this file is never read by the page.",
        "confirmed": sorted(confirmed), "conflicts": conflicts, "disagree_with_confirmed": disagree,
        "alerts": sorted(alerts.values(), key=lambda a: a["first_seen"], reverse=True)[:50],
        "candidates": sorted(cands.values(), key=lambda c: (c["state"], c["first_seen"])),
        "pre_close_urls": sorted(pre_close),
    }
    _write_atomic(CANDIDATES, out)
    return out


def monitor(interval: float, once: bool, baseline: bool = False) -> int:
    roster, close = load_roster()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    pid_file = RUN_DIR / "calls_monitor.pid"
    persistent = not once and not baseline
    if persistent:
        try:
            old = int(pid_file.read_text())
            os.kill(old, 0)
            if "election.calls" in Path(f"/proc/{old}/cmdline").read_text(errors="ignore").replace("\0", " "):
                print(f"call monitor already running (pid {old})")
                return 0
        except (OSError, ValueError):
            pass
        pid_file.write_text(str(os.getpid()))
        STOP_FILE.unlink(missing_ok=True)
    cycle = 0
    try:
        while True:
            out = run_cycle(cycle, roster, close, baseline=baseline)
            print(f"--- {out['updated_at']} cycle {cycle}: {out['queries']} queries, searx_ok={out['searx_ok']}, "
                  f"{len(out['candidates'])} candidates, conflicts={out['conflicts']}, "
                  f"disagree={out['disagree_with_confirmed']}, alerts={len(out['alerts'])}", flush=True)
            for c in out["candidates"]:
                if c["last_seen"] == out["updated_at"] and c["state"] not in out["confirmed"]:
                    print(f"  {c['state']} {c['key']:<12} {c['outlet']:<18} {c['published'] or '?':<22} {c['url']}", flush=True)
            cycle += 1
            if once or baseline:
                return 0
            deadline = time.monotonic() + max(interval, 120.0)
            while time.monotonic() < deadline:
                if STOP_FILE.exists():
                    print("STOP file: call monitor exiting", flush=True)
                    return 0
                time.sleep(5)
    finally:
        if persistent:
            pid_file.unlink(missing_ok=True)


# ---------------------------------------------------------------- confirm / retract / list (humans only)

AT_RE = re.compile(r"^(by )?(1[0-2]|0?[1-9]):[0-5]\d (AM|PM) ET$")   # "by ..." = reported by then (AP gave no time)


def confirm(state: str, key: str, url: str, outlet: str, at: str, by: str, replace: bool = False,
            now: dt.datetime | None = None) -> dict:
    roster, close = load_roster()
    state, now = state.upper(), now or now_utc()
    if state not in roster:
        raise SystemExit(f"{state}: no 2026 Senate race")
    cand = next((c for c in roster[state] if c.key == key), None)
    if cand is None:
        raise SystemExit(f"{state}: unknown candidate key {key!r}; choose from {[c.key for c in roster[state]]}")
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname:
        raise SystemExit("--url must be the https:// link of the published story")
    if not (outlet_of(url) == outlet.lower() or outlet_of(url).endswith("." + outlet.lower())):
        raise SystemExit(f"--outlet {outlet!r} is not the story's site ({outlet_of(url)})")
    if not AT_RE.match(at):
        raise SystemExit('--at must look like "10:42 PM ET" (the time AP declared, Eastern)')
    if now < close[state]:
        raise SystemExit(f"{state}: polls have not all closed yet ({close[state].isoformat()}); AP does not call before")
    with _Lock(CALLS):
        doc = _read(CALLS, {}) or {}
        calls = doc.setdefault("calls", {})
        cur = calls.get(state)
        if cur and not cur.get("retracted") and cur.get("key") != key and not replace:
            raise SystemExit(f"{state} is already confirmed for {cur['key']!r}. If AP changed its call, run "
                             f"`retract {state}` first (the stream must say so), or pass --replace")
        entry = {"state": state, "key": key, "name": cand.name, "party": cand.party, "source": "AP",
                 "url": url, "outlet": outlet.lower(), "at": at, "confirmed_at": iso(now), "confirmed_by": by}
        calls[state] = entry
        doc.setdefault("history", []).append({"action": "confirm", **entry})
        doc["updated_at"] = iso(now)
        _write_atomic(CALLS, doc)
    return entry


def retract(state: str, reason: str, by: str, now: dt.datetime | None = None) -> dict:
    state, now = state.upper(), now or now_utc()
    with _Lock(CALLS):
        doc = _read(CALLS, {}) or {}
        cur = (doc.get("calls") or {}).get(state)
        if not cur or cur.get("retracted"):
            raise SystemExit(f"{state}: no confirmed call to retract")
        cur.update(retracted=True, retracted_at=iso(now), retract_reason=reason, retracted_by=by)
        doc.setdefault("history", []).append({"action": "retract", "state": state, "key": cur["key"], "at_utc": iso(now),
                                              "reason": reason, "by": by})
        doc["updated_at"] = iso(now)
        _write_atomic(CALLS, doc)
    return cur


def show() -> None:
    doc = _read(CALLS, {}) or {}
    print(f"confirmed calls ({CALLS}):")
    for st, c in sorted((doc.get("calls") or {}).items()):
        flag = f"  RETRACTED {c.get('retracted_at')} ({c.get('retract_reason')})" if c.get("retracted") else ""
        print(f"  {st} {c['key']:<12} {c.get('at', ''):<12} via {c.get('outlet', ''):<16} {c.get('url', '')}{flag}")
    cd = _read(CANDIDATES, {}) or {}
    print(f"\ncandidates ({CANDIDATES}, updated {cd.get('updated_at')}, searx_ok={cd.get('searx_ok')}):")
    live = {st for st, c in (doc.get("calls") or {}).items() if not c.get("retracted")}
    for c in cd.get("candidates", []):
        mark = "  (confirmed)" if c["state"] in live else ""
        print(f"  {c['state']} {c['key']:<12} {c['matched_by']:<14} {c['outlet']:<18} {c.get('published') or '?':<22} "
              f"{c['headline'][:70]!r} {c['url']}{mark}")
        for w in c.get("warnings", []):
            print(f"      ! {w}")
    for k, title in (("conflicts", "CONFLICT (several winners for one state)"), ("disagree_with_confirmed", "DISAGREES WITH A CONFIRMED CALL")):
        if cd.get(k):
            print(f"\n{title}: {cd[k]}")
    for a in cd.get("alerts", [])[:10]:
        print(f"\nPOSSIBLE RETRACTION: {a['states']} {a['headline']!r} {a['url']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m election.calls", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("monitor", help="search for AP race-call stories; writes call_candidates.json only")
    m.add_argument("--interval", type=float, default=float(os.environ.get("ELECTION_CALLS_INTERVAL_S", "300")))
    m.add_argument("--once", action="store_true")
    sub.add_parser("baseline", help="one pass over all 35 states before polls close: mark existing stories as old")
    c = sub.add_parser("confirm", help="a human confirms an AP declaration they have read")
    c.add_argument("state")
    c.add_argument("key")
    c.add_argument("--url", required=True)
    c.add_argument("--outlet", required=True)
    c.add_argument("--at", required=True, help='time AP declared, e.g. "10:42 PM ET"')
    c.add_argument("--by", default=os.environ.get("USER", "operator"))
    c.add_argument("--replace", action="store_true", help="replace a confirmed call for another candidate")
    r = sub.add_parser("retract", help="remove a call at once (AP retracted it, or the report is ambiguous)")
    r.add_argument("state")
    r.add_argument("--reason", default="AP retracted its call")
    r.add_argument("--by", default=os.environ.get("USER", "operator"))
    sub.add_parser("list", help="confirmed calls and current candidates")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if a.cmd in ("monitor", "baseline"):
        if str(REPO / "src") not in sys.path:
            sys.path.insert(0, str(REPO / "src"))
        return monitor(getattr(a, "interval", 300), getattr(a, "once", False), baseline=a.cmd == "baseline")
    if a.cmd == "confirm":
        e = confirm(a.state, a.key, a.url, a.outlet, a.at, a.by, a.replace)
        print(f"confirmed {e['state']} {e['key']} ({e['name']}): Race call: The Associated Press (via {e['outlet']}), "
              f"{e['at']} -> {CALLS}")
        return 0
    if a.cmd == "retract":
        e = retract(a.state, a.reason, a.by)
        print(f"RETRACTED {e['state']} {e['key']} -> {CALLS}. The stream must say on air that the call was withdrawn.")
        return 0
    show()
    return 0


if __name__ == "__main__":
    sys.exit(main())

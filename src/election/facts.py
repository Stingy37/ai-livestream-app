"""Fact sheets: what the writer may say on each visual, built from a snapshot (the same data the page draws).

A fact sheet is {visual: [fact, ...]}; the writer may only state a number on a beat if that number is in the beat's
own visual facts (or the global allowance), which is what keeps the narration on the graphic that is on screen.
"""
from __future__ import annotations

from datetime import datetime, timezone

from election.snapshot import fmt_et

STATE_ORDER = {
    "preview": ["st_intro", "st_senators", "st_candidates", "st_history", "st_poll_close"],
    "awaiting": ["st_intro", "st_results", "st_senators", "st_candidates", "st_history"],
    "counting": ["st_intro", "st_results", "st_counties", "st_votes_left", "st_history", "st_candidates", "st_senators"],
    "declared": ["st_intro", "st_results", "st_counties", "st_history", "st_candidates", "st_senators"],
}
NATIONAL_ORDER = ["nat_balance", "nat_map", "nat_races", "nat_schedule"]


def _p(x) -> str:
    return "n/a" if x is None else f"{x:.1f}%"


def state_phase(s: dict) -> str:
    if s["phase"] == "preview":
        return "preview"
    if not s["results_available"]:
        return "awaiting"
    return s["phase"]


def state_facts(s: dict, lang: str, now: datetime | None = None) -> dict[str, list[str]]:
    now = now or datetime.now(timezone.utc)
    ph = state_phase(s)
    nm = s["state_name"]
    cards = s["cards"]
    names = ", ".join(f"{c['name']} ({c['party_label']}{', incumbent' if c['incumbent'] else ''})" for c in cards)
    main, last = fmt_et(s["poll_close"]["main_et"], lang), fmt_et(s["poll_close"]["last_et"], lang)
    up = next((x for x in s["senators"] if x["up"]), None)
    F: dict[str, list[str]] = {}
    intro = [f"State: {nm}. Race: US Senate{' special election' if s['special'] else ''} ({s['race_label']}).",
             f"Candidates on the card: {names}."]
    if up:
        intro.append(f"The seat on the ballot is held by {up['name']} ({up['party_label']}), in office since {up['since']}; "
                     f"{'running again' if up['running'] else 'not on the ballot'}.")
    if ph == "preview":
        intro.append(f"Polls close at {main}" + (f"; the last polls in the state close at {last}." if main != last else "."))
        intro.append("No results may be mentioned: polls are still open.")
    else:
        intro.append(f"All polls in the state have closed (last closing {last}).")
    if s["rcv"]:
        intro.append(f"Ranked-choice voting: {s['rcv_note']}")
    F["st_intro"] = intro

    F["st_senators"] = [f"Senator {x['name']} ({x['party_label']}), in office since {x['since']}; "
                        + ("this seat is on the ballot in 2026" if x["up"] else f"next election {x['next_election']}")
                        + (f"; {x['note']}" if x.get("note") else "") + f" [focus id \"{i}\"]" for i, x in enumerate(s["senators"])]
    cf = []
    for c in cards:
        bits = [f"{c['name']} ({c['party_label']}{', incumbent' if c['incumbent'] else ''})"]
        if c.get("role"):
            bits.append(f"current/most recent role: {c['role']}")
        if c.get("age"):
            bits.append(f"age {c['age']}")
        cf.append("; ".join(bits) + f" [focus id \"{c['key']}\"]")
        cf += [f"  {c['short']} background: {t}" for t in c["facts"]]
        cf += [f"  {c['short']} position (attribute it to the candidate): {t}" for t in c["positions"]]
    F["st_candidates"] = cf

    h = s["history"]
    hp, hs = h["pres2024"], h["sen_prev"]
    hist = [f"2024 presidential result in {nm}: {hp['rep_name']} (Republican) {hp['rep_pct']:.1f}% ({hp['rep']} votes), "
            f"{hp['dem_name']} (Democratic) {hp['dem_pct']:.1f}% ({hp['dem']} votes); margin {abs(hp['rep_pct'] - hp['dem_pct']):.1f} points.",
            f"Previous election for this seat ({hs['year']}): {hs['rep_name']} (Republican) {hs['rep_pct']:.1f}%, {hs['dem_name']} "
            f"({'independent backed by Democrats' if hs.get('dem_is_independent') else 'Democratic'}) {hs['dem_pct']:.1f}%; "
            f"margin {abs(hs['rep_pct'] - hs['dem_pct']):.1f} points.",
            f"Total votes cast in the 2022 midterm in {nm}: {h['turnout2022']}."]
    rows = {r["id"]: r for r in s["units"]["rows"]}
    for uid in s["callouts"]:
        hu = h["units"].get(uid)
        if hu:
            p = hu["pres2024"]
            hist.append(f"{rows[uid]['name']} [focus id \"{uid}\"]: 2024 {hp['rep_name']} {p['rep_pct']:.1f}%, {hp['dem_name']} "
                        f"{p['dem_pct']:.1f}% (margin {hu['margin_pts']:.1f} points); 2022 midterm votes cast {rows[uid]['turnout2022']}.")
    F["st_history"] = hist

    if ph == "preview":
        F["st_poll_close"] = [f"Polls in {nm} close at {main}" + (f"; the last polls close at {last}." if main != last else "."),
                              "Until then no results are reported."]
        return F

    src = f"Source: {s['source']}, unofficial results" + (" (first-choice votes)" if s["rcv"] else "")
    if not s["results_available"]:
        F["st_results"] = [f"{src}: no official count has been published yet by {s['source']} (say so plainly; give no numbers)."]
        if s.get("call_retracted"):
            F["st_results"].append("CORRECTION: AP has withdrawn its earlier declaration in this race; say so plainly.")
        elif s["call"]:
            F["st_results"].append(f"AP declaration (relay exactly, attributed to AP): {s['call']['text']}")
        return F
    res = [src + "."]
    for c in s["candidates"]:
        if not c.get("on_card") and (c["pct"] or 0) < 1:
            continue
        res.append(f"{c['name']} ({c['party_label']}): {c['votes']} votes, {_p(c['pct'])} [focus id \"{c['key']}\"]")
    lead = s["candidates"][0]
    if len(s["candidates"]) > 1 and lead.get("ahead_by") is not None:
        res.append(f"{lead['short']} leads by {lead['ahead_by']} votes, {lead['ahead_pts']:.1f} points, in the official count so far.")
    res.append(f"Total votes counted so far: {s['total_votes']}.")
    if s.get("precincts") and s["precincts"].get("total"):
        pr = s["precincts"]
        res.append(f"Precincts reporting: {pr['reporting']} of {pr['total']} ({100 * pr['reporting'] / pr['total']:.1f}%).")
    if s.get("call_retracted"):
        res.append("CORRECTION: AP has withdrawn its earlier declaration in this race; say plainly that the earlier "
                   "AP race call we reported has been withdrawn and that no winner is declared.")
    if s["call"]:
        res.append(f"AP declaration (relay exactly, attributed to AP): {s['call']['text']}")
    else:
        res.append("No race call: say who leads, never who will win.")
    F["st_results"] = res

    cnt = []
    reported = [r for r in s["units"]["rows"] if r["total"]]
    cnt.append(f"{len(reported)} of {len(s['units']['rows'])} {'districts' if s['units']['type'] == 'house_district' else 'counties'} have reported votes.")
    keyname = {c["key"]: c["short"] for c in s["candidates"]}
    for uid in s["callouts"]:
        r = rows[uid]
        hu = h["units"].get(uid, {}).get("pres2024", {})
        if r["total"]:
            cnt.append(f"{r['name']} [focus id \"{uid}\"]: {r['total']} votes counted, {keyname.get(r['leader'], r['leader'])} leads by "
                       f"{r['margin_pts']:.1f} points; counted so far = {r['counted_vs_2022_pct']:.1f}% of its 2022 total; "
                       f"in 2024 {hp['rep_name']} {hu.get('rep_pct', 0):.1f}%, {hp['dem_name']} {hu.get('dem_pct', 0):.1f}%.")
        else:
            cnt.append(f"{r['name']} [focus id \"{uid}\"]: no votes reported yet; in 2024 {hp['rep_name']} {hu.get('rep_pct', 0):.1f}%, "
                       f"{hp['dem_name']} {hu.get('dem_pct', 0):.1f}%.")
    F["st_counties"] = cnt
    cv = s["counted_vs_2022"]
    vl = [f"Votes counted so far statewide: {cv['counted']}, equal to {cv['pct']:.1f}% of the {cv['total2022']} votes cast in the 2022 midterm "
          "(a comparison only: never say how many votes remain or what share of the vote is in)."]
    for r in s["votes_left"]:
        vl.append(f"{r['name']} [focus id \"{r['id']}\"]: counted so far {r['counted']} = {(r['pct'] or 0):.1f}% of its 2022 total of {r['total2022']}.")
    F["st_votes_left"] = vl
    return F


def national_facts(n: dict, lang: str, now: datetime | None = None) -> dict[str, list[str]]:
    b = n["balance"]
    races = n["races"]
    rdef = sum(1 for r in races if r["incumbent_party"] == "REP")
    ddef = sum(1 for r in races if r["incumbent_party"] in ("DEM", "IND"))
    F = {"nat_balance": [
        "Senate before the election: 53 Republicans, 45 Democrats, 2 independents who caucus with the Democrats.",
        f"{b['up']} seats are on the ballot today; Republicans hold {rdef} of them, Democrats {ddef}.",
        f"Seats not on the ballot: Republicans {b['holdover']['REP']}, Democrats {b['holdover']['DEM']}, independents {b['holdover']['IND']}.",
        f"{b['majority']} seats make a majority; with 50-50 the Vice President breaks ties.",
        f"Races declared by AP so far: Republicans {b['declared']['REP']}, Democrats {b['declared']['DEM']}, others {b['declared']['IND']}; "
        f"undeclared {b['undecided']}.",
        *([f"AP report (relay exactly once, attributed to AP, no adjectives): The Associated Press reports that the "
           f"{'Democrats' if n['control']['party'] == 'DEM' else 'Republicans'} have won control of the Senate."]
          if n.get("control") else []),
        "Important caveat to say once: this tally includes only the AP declarations this broadcast has confirmed from news "
        "reports so far; AP may already have declared more races that are not yet shown here."]}
    counts = {}
    for r in races:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    m = [f"Status of the {len(races)} Senate races: " + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in counts.items()) + "."]
    for r in races:
        if r["status"] == "declared":
            m.append(f"{r['state_name']} [focus id \"{r['state']}\"]: AP has declared {r['declared']['short']} ({r['declared']['party']}) the winner.")
    m.append("Featured states tonight: Texas, Alaska, Kansas, Maine, Ohio (special election), Michigan.")
    F["nat_map"] = m
    nr = []
    for r in races:
        if not r["featured"]:
            continue
        line = f"{r['state_name']} [focus id \"{r['state']}\"]: "
        if r["status"] == "polls_open":
            line += f"polls open; last polls close at {fmt_et(r['poll_close_last_et'], lang)}."
        elif r["status"] == "declared":
            line += f"AP has declared {r['declared']['short']} the winner."
        elif r["leader"]:
            line += f"{r['leader']['short']} leads with {r['leader']['pct']:.1f}% in the official count so far."
        else:
            line += "polls closed; no official count published yet."
        nr.append(line)
    F["nat_races"] = nr
    now = now or datetime.now(timezone.utc)
    sch = []
    for x in n["schedule"]:
        t = datetime.fromisoformat(x["et"])
        tag = "closed" if t <= now else "upcoming"
        sch.append(f"{fmt_et(x['et'], lang)} [{tag}]: " + ", ".join(x["states"]))
    F["nat_schedule"] = sch
    return F

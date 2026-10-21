"""Offline test of the whole graph: fake fetcher, fake SearXNG and a fake model drive search -> verify -> experts
-> search for three rounds without any network."""

import json
from datetime import datetime, timezone

from contracts import Scene

import scraper.web_scraper as ws_module
from scraper.fetch import FetchResult
from scraper.graph import ScrapeGraph
from scraper.searx import SearchHit
from scraper.verify import BaselineRule

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)

PAGES = {
    "https://agency.example/bulletin": FetchResult(url="https://agency.example/bulletin", ok=True, status=200, content_type="text/html",
                                                   text="PAGASA reports maximum sustained winds of 185 km/h. " * 5, title="bulletin",
                                                   published_at=NOW, extraction="trafilatura", fetched_at=NOW),
    "https://news.example/a": FetchResult(url="https://news.example/a", ok=True, status=200, content_type="text/html",
                                          text="JMA says the typhoon is moving WNW at 20 km/h. " * 5, title="a", published_at=NOW,
                                          extraction="trafilatura", fetched_at=NOW),
    "https://news.example/b": FetchResult(url="https://news.example/b", ok=False, status=404, error="HTTP 404"),
}


class FakeFetcher:
    def __init__(self):
        self.calls = []
        self.stats = {"fetched": 0, "cache_hits": 0, "failed": 0}

    def fetch_many(self, urls):
        self.calls.append(list(urls))
        return [PAGES.get(u, FetchResult(url=u, ok=False, error="unknown")) for u in urls]


class FakeSearx:
    base_url = "http://fake"

    def __init__(self):
        self.queries = []
        self.stats = {"queries": 0, "results": 0, "errors": 0}

    def available(self):
        return True

    def search(self, query, time_range=None, language="en"):
        self.queries.append(query)
        return [SearchHit("https://news.example/a", "a", "", "ddg", query), SearchHit("https://news.example/b", "b", "", "ddg", query)]


def fake_ask(system, user):
    """A model that never finds the pool sufficient, so the loop runs all rounds."""
    if "coverage checklist" in system:
        return json.dumps({"checklist": ["sustained_wind", "movement", "evacuation"]})
    if "research planner" in system:
        return 'Thought: look for evacuations.\nAction: {"queries": ["champi evacuation %d"], "follow_urls": [], "time_range": "day"}' % len(user)
    if "judging whether" in system:
        return json.dumps({"sufficient": False, "missing": ["evacuation orders"], "covered": ["winds"]})
    if "extract factual claims" in system:
        if "185 km/h" in user:
            return json.dumps({"claims": [{"quote": "maximum sustained winds of 185 km/h", "agency": "PAGASA", "quantity_type": "sustained_wind", "value": "185", "unit": "km/h", "time": ""}]})
        return json.dumps({"claims": [{"quote": "moving WNW at 20 km/h", "agency": "JMA", "quantity_type": "movement", "value": "20", "unit": "km/h", "time": ""},
                                      {"quote": "evacuation of 5,000 people", "agency": "JMA", "quantity_type": "evacuation", "value": "5000", "unit": "", "time": ""}]})  # not in text -> dropped
    if "compare claims" in system:
        return json.dumps({"conflicts": []})
    if "ordinary resident" in system:
        return json.dumps({"unclear_wording": ["WNW"], "missing_actions": ["whether to evacuate"], "search_suggestions": ["evacuation advisory Batanes"]})
    if "specialist" in system:
        return json.dumps({"notes": ["winds 185 km/h quoted"], "gaps": ["evacuations"], "unreported_figures": ["rainfall totals"], "search_suggestions": ["NDRRMC evacuation champi"]})
    raise AssertionError("unexpected prompt: " + system[:60])


def test_graph_loops_search_verify_experts_and_never_keeps_invented_claims():
    fetcher, searx = FakeFetcher(), FakeSearx()
    g = ScrapeGraph(fetcher, searx, fake_ask, max_threads=2, max_rounds=3, react_inner_rounds=1, max_pages=5, rule=BaselineRule())
    scene = {"id": "s1", "node_key": "impacts", "title": "Local Impacts", "topic": "impacts", "sources": ["https://agency.example/bulletin"], "language": "en"}
    state = g.run(scene, web_search=True)
    # round 1 finds news/a, round 2 finds nothing new (same hits) -> the graph stops before spending a third round
    assert state["round"] == 2 and state["end_reason"] == "last search round found nothing new"
    assert fetcher.calls[0] == ["https://agency.example/bulletin"]          # user source fetched first
    assert len(searx.queries) == 2 and len(state["queries_done"]) == 2    # one new query per round
    assert [d.url for d in state["docs"]] == ["https://agency.example/bulletin", "https://news.example/a"]
    assert "https://news.example/b" in state["urls_done"] and any(e["url"].endswith("/b") and not e["ok"] for e in state["fetch_log"])
    assert sum(1 for u in fetcher.calls[1:] for x in u if x == "https://news.example/a") == 1  # never fetched twice
    v = state["verify"]
    assert {c.quantity_type for c in v.claims} == {"sustained_wind", "movement"} and v.dropped_claims >= 1   # invented evacuation dropped
    assert state["baseline"]["missing"] == ["evacuation"] and not state["baseline"]["passed"]
    assert len(state["experts"]) == 1 and state["experts"][0]["citizen"]["missing_actions"] == ["whether to evacuate"]
    assert state["docs"][0].metadata["verify"]["claims"] == 1 and state["docs"][0].metadata["verify"]["stale"] is False
    steps = [t["step"] for t in state["trace"]]
    assert steps == ["seed", "search", "verify", "experts", "search", "verify"]
    assert state["trace"][1]["new_docs"] == 1 and state["trace"][4]["new_docs"] == 0


def test_graph_uses_all_three_rounds_while_new_documents_keep_arriving():
    class GrowingSearx(FakeSearx):
        def search(self, query, time_range=None, language="en"):
            self.queries.append(query)
            n = len(self.queries)
            PAGES[f"https://news.example/n{n}"] = FetchResult(url=f"https://news.example/n{n}", ok=True, status=200, content_type="text/html",
                                                              text="JMA says winds of 100 kt. " * 5, title=f"n{n}", published_at=NOW, extraction="trafilatura", fetched_at=NOW)
            return [SearchHit(f"https://news.example/n{n}", f"n{n}", "", "ddg", query)]

    g = ScrapeGraph(FakeFetcher(), GrowingSearx(), fake_ask, max_threads=2, max_rounds=3, react_inner_rounds=1)
    scene = {"id": "s1", "node_key": "impacts", "title": "Local Impacts", "topic": "impacts", "sources": [], "language": "en"}
    state = g.run(scene, web_search=True)
    assert state["round"] == 3 and state["end_reason"] == "3 rounds used" and len(state["experts"]) == 2
    assert [t["step"] for t in state["trace"]] == ["seed", "search", "verify", "experts", "search", "verify", "experts", "search", "verify"]


def test_graph_without_web_search_or_links_stops_after_first_verify():
    fetcher = FakeFetcher()
    g = ScrapeGraph(fetcher, None, fake_ask, max_threads=2, max_rounds=3, react_inner_rounds=2)
    scene = {"id": "s1", "node_key": "position", "title": "Current Position", "topic": "position", "sources": ["https://agency.example/bulletin"], "language": "en"}
    state = g.run(scene, web_search=False)
    assert state["round"] == 1 and "nothing more can be fetched" in state["end_reason"]
    assert [t["step"] for t in state["trace"]] == ["seed", "search", "verify"]
    assert state["trace"][1]["react"][0]["note"].startswith("no web search")


def test_web_scraper_wires_report_and_flag(monkeypatch):
    monkeypatch.setenv("SCRAPE_WEB_SEARCH_SCENES", "impacts")
    scene = Scene(id="x", node_key="impacts", title="Local Impacts", topic_description="impacts", system_instructions="",
                  sources=["https://agency.example/bulletin"], language="en", script_model="m", tts_model="k", tts_voice="v")
    assert ws_module.web_search_allowed(scene)
    scene.node_key = "position"
    assert not ws_module.web_search_allowed(scene)
    scene.sources = []
    assert ws_module.web_search_allowed(scene)

    ws = ws_module.WebScraper(max_threads=2)
    ws._fetcher, ws._searx = FakeFetcher(), FakeSearx()
    ws._graph = ScrapeGraph(ws._fetcher, ws._searx, fake_ask, max_threads=2, max_rounds=1, react_inner_rounds=1)
    docs = ws.gather(scene)
    assert [d.url for d in docs] == ["https://news.example/a"]
    rep = ws.last_report
    assert rep["rounds"] == 1 and rep["urls_failed"] == ["https://news.example/b"] and rep["checklist"] == ["sustained_wind", "movement", "evacuation"]
    assert rep["documents"][0]["verify"]["claims"] == 1 and rep["baseline"]["passed"] is False
    json.dumps(rep)  # must be serialisable for scrape_report.json

"""The search chain in scraper.searx: SearXNG, then Tavily (capped), then ddgs (opt-in). No network: a fake session."""

import sys
import types

import pytest

from scraper import searx as S


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data if data is not None else {}
        self.ok = status < 400

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Session:
    """searx: a list of Resp / Exception, one per SearXNG call (the last repeats); tavily: same for Tavily."""

    def __init__(self, searx=(), tavily=()):
        self.searx, self.tavily = list(searx), list(tavily)
        self.gets, self.posts = [], []

    @staticmethod
    def _next(queue):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, params=None, timeout=None):
        self.gets.append(params)
        return self._next(self.searx)

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return self._next(self.tavily)


def results(*urls, engine="duckduckgo"):
    return Resp(200, {"results": [{"url": u, "title": u, "content": "c", "engine": engine} for u in urls]})


def client(session, **kw):
    kw.setdefault("tavily_key", "tvly-test")
    kw.setdefault("ddgs", False)
    c = S.SearxClient(base_url="http://searx.local", **kw)
    c._session = session
    return c


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch):
    for name in ("TAVILY_API_KEY", "SCRAPE_DDGS_FALLBACK", "SCRAPE_TAVILY_MAX_CREDITS"):
        monkeypatch.delenv(name, raising=False)


def test_searxng_answers_no_paid_search():
    s = Session(searx=[results("https://news.example/a")], tavily=[results("https://t.example/x")])
    hits = client(s).search("typhoon")
    assert [h.url for h in hits] == ["https://news.example/a"] and not s.posts


def test_error_falls_back_to_tavily_and_filters_its_results():
    s = Session(searx=[RuntimeError("timeout")],
                tavily=[results("https://www.youtube.com/watch?v=1", "https://agency.example/bulletin", engine="")])
    c = client(s)
    hits = c.search("typhoon", time_range="day")
    assert [(h.url, h.engine) for h in hits] == [("https://agency.example/bulletin", "tavily")]
    post = s.posts[0]
    assert post["headers"] == {"Authorization": "Bearer tvly-test"}
    assert post["json"]["search_depth"] == "basic" and post["json"]["time_range"] == "day"
    assert c.stats["tavily"] == 1 and c.stats["tavily_credits"] == 1 and c.stats["errors"] == 1


def test_empty_searxng_falls_back():
    s = Session(searx=[results("https://www.facebook.com/p")], tavily=[results("https://agency.example/a")])
    assert [h.url for h in client(s).search("q")] == ["https://agency.example/a"]


def test_one_error_does_not_switch_searxng_off():
    """Nirvaan's chain switched SearXNG off after one error, so every later query went to Tavily (paid)."""
    s = Session(searx=[RuntimeError("slow"), results("https://news.example/a")], tavily=[results("https://t.example/x")])
    c = client(s)
    c.search("q0")                                   # error -> Tavily
    for i in range(1, 9):
        c.search(f"q{i}")                            # SearXNG healthy again
    assert len(s.gets) == 9 and c.stats["tavily_credits"] == 1 and c.stats["searxng"] == 8


def test_errors_in_a_row_cool_searxng_down_then_retry(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(S.time, "monotonic", lambda: now[0])
    s = Session(searx=[RuntimeError("down")], tavily=[results("https://t.example/x")])
    c = client(s, tavily_max_credits=50)
    c.search("a"); c.search("b")                     # 2 errors in a row -> cooldown
    assert len(s.gets) == 2 and c.stats["searx_cooldowns"] == 1
    c.search("c")                                    # cooling down: straight to Tavily
    assert len(s.gets) == 2
    now[0] += c.searx_cooldown_s + 1
    s.searx = [results("https://news.example/a")]
    assert c.search("d")[0].engine == "duckduckgo" and len(s.gets) == 3


def test_tavily_credit_cap():
    s = Session(searx=[results()], tavily=[results()])          # nothing anywhere
    c = client(s, tavily_max_credits=2)
    for i in range(5):
        assert c.search(f"q{i}") == []
    assert len(s.posts) == 2 and c.stats["tavily_credits"] == 2 and "cap" in c._tavily_off


@pytest.mark.parametrize("status", [401, 432, 433])
def test_bad_key_or_spent_plan_switches_tavily_off(status):
    s = Session(searx=[RuntimeError("down")], tavily=[Resp(status)])
    c = client(s, tavily_max_credits=50)
    c.searx_fail_limit = 99
    c.search("a"); c.search("b"); c.search("c")
    assert len(s.posts) == 1 and str(status) in c._tavily_off


def test_rate_limit_skips_tavily_for_that_query_only():
    s = Session(searx=[RuntimeError("down")], tavily=[Resp(429), results("https://t.example/x")])
    c = client(s, tavily_max_credits=50)
    c.searx_fail_limit = 99
    assert c.search("a") == [] and c.search("b")[0].url == "https://t.example/x" and not c._tavily_off


def test_no_key_and_ddgs_off_by_default(monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)               # importing it would fail loudly
    s = Session(searx=[RuntimeError("down")])
    c = S.SearxClient(base_url="http://searx.local")
    c._session = s
    assert c.fallbacks() == [] and c.search("q") == [] and not s.posts and c.stats["no_results"] == 1


def test_ddgs_when_switched_on(monkeypatch):
    class DDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, max_results=None):
            return [{"href": "https://www.instagram.com/x", "title": "i", "body": ""},
                    {"href": "https://news.example/d", "title": "d", "body": "b"}]

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=DDGS))
    monkeypatch.setenv("SCRAPE_DDGS_FALLBACK", "1")
    s = Session(searx=[RuntimeError("down")])
    c = S.SearxClient(base_url="http://searx.local", tavily_key="")
    c._session = s
    hits = c.search("q")
    assert [(h.url, h.engine) for h in hits] == [("https://news.example/d", "ddgs")] and c.stats["ddgs"] == 1


def test_available_with_and_without_fallback():
    down = Session(searx=[RuntimeError("refused")])
    assert client(down, tavily_key="").available() is False
    c = client(Session(searx=[RuntimeError("refused")], tavily=[results("https://t.example/x")]))
    assert c.available() is True
    assert c.search("q")[0].engine == "tavily" and len(c._session.gets) == 1   # the probe only: cooling down
    up = client(Session(searx=[Resp(200, {"results": []})]), tavily_key="")
    assert up.available() is True

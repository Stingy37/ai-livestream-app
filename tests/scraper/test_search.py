"""Offline tests for search: SearXNG and ddgs are both faked."""

import httpx
import pytest

from scraper.search import DDGS_BACKENDS, Searcher, SearchResult


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.payload = payload or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)


@pytest.fixture
def ddgs_results(monkeypatch):
    calls = []

    def fake(self, query):
        calls.append(query)
        return [SearchResult("https://ddg.example/a", "A", "snip", "ddgs")]

    monkeypatch.setattr(Searcher, "ddgs", fake)
    return calls


def test_searxng_results_are_parsed(monkeypatch):
    payload = {"results": [{"url": "https://a.example", "title": "A", "content": "about a"}, {"title": "no url"}]}
    seen = {}

    def fake_get(url, params, **kwargs):
        seen.update(url=url, params=params)
        return FakeResponse(200, payload)

    monkeypatch.setattr(httpx, "get", fake_get)
    results = Searcher(base_url="http://searx.local/").search("typhoon")
    assert results == [SearchResult("https://a.example", "A", "about a", "searxng")]
    assert seen == {"url": "http://searx.local/search", "params": {"q": "typhoon", "format": "json"}}


def test_unset_url_falls_back_to_ddgs(monkeypatch, ddgs_results, caplog):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    searcher = Searcher()
    assert searcher.search("q")[0].engine == "ddgs"
    assert "SEARXNG_URL is not set" in caplog.text


def test_json_disabled_falls_back_and_stays_down(monkeypatch, ddgs_results, caplog):
    gets = []
    monkeypatch.setattr(httpx, "get", lambda *a, **k: gets.append(1) or FakeResponse(403))
    searcher = Searcher(base_url="http://searx.local")
    searcher.search("one")
    searcher.search("two")
    assert len(gets) == 1  # SearXNG is not asked again after it failed
    assert ddgs_results == ["one", "two"]
    assert "JSON API is disabled" in caplog.text


def test_both_engines_failing_returns_nothing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(Searcher, "ddgs", boom)
    assert Searcher(base_url="http://searx.local").search("q") == []


def test_ddgs_retries_with_other_backends(monkeypatch):
    import ddgs

    tried = []

    class FakeDDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, max_results, backend):
            tried.append(backend)
            if backend == "auto":
                raise ddgs.exceptions.DDGSException("No results found.")
            return [{"href": "https://yahoo.example/a", "title": "A", "body": "b"}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    results = Searcher(base_url="").search("q")
    assert tried == list(DDGS_BACKENDS)
    assert [r.url for r in results] == ["https://yahoo.example/a"]


def test_results_are_cached_between_runs(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(Searcher, "_search_network", lambda self, q: calls.append(q) or [SearchResult("https://a", "A", "s", "ddgs")])
    first = Searcher(base_url="", cache_dir=tmp_path).search("q")
    second = Searcher(base_url="", cache_dir=tmp_path).search("q")  # a later run, e.g. a regeneration cycle
    assert first == second and calls == ["q"]


def test_empty_results_are_not_cached(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(Searcher, "_search_network", lambda self, q: calls.append(q) or [])
    searcher = Searcher(base_url="", cache_dir=tmp_path)
    searcher.search("q")
    searcher.search("q")
    assert calls == ["q", "q"]  # a block may be temporary, so it is asked again


def test_network_searches_are_spaced_out(monkeypatch, tmp_path):
    from scraper import search

    monkeypatch.setattr(search, "MIN_INTERVAL", 1.0)
    waits = []
    monkeypatch.setattr(search.time, "sleep", waits.append)
    monkeypatch.setattr(Searcher, "_search_network", lambda self, q: [])
    searcher = Searcher(base_url="", cache_dir=tmp_path)
    searcher.search("a")
    searcher.search("b")
    assert len(waits) == 1 and 0 < waits[0] <= 1.0


def test_ddgs_empty_answer_tries_next_backend(monkeypatch):
    import ddgs

    tried = []

    class FakeDDGS:
        def __init__(self, timeout=None):
            pass

        def text(self, query, max_results, backend):
            tried.append(backend)
            return [] if backend == "auto" else [{"href": "https://y.example", "title": None, "body": None}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    [result] = Searcher(base_url="").search("q")
    assert tried == list(DDGS_BACKENDS)
    assert result.title == "" and result.snippet == ""  # None from the engine becomes ""


# ── SearXNG -> Tavily -> ddgs chain ─────────────────────────────────────────


class FakeNet:
    """Fake SearXNG (httpx.get) and Tavily (httpx.post) that record their calls."""

    def __init__(self, monkeypatch, searxng, tavily):
        self.searxng_calls, self.tavily_calls = [], []
        self.searxng, self.tavily = list(searxng), list(tavily)
        monkeypatch.setattr(httpx, "get", self.get)
        monkeypatch.setattr(httpx, "post", self.post)

    def get(self, url, params, **kwargs):
        self.searxng_calls.append(params["q"])
        return self.searxng.pop(0)

    def post(self, url, headers, json, **kwargs):
        self.tavily_calls.append({"url": url, "headers": headers, "json": json})
        return self.tavily.pop(0)


def hits(engine_field, *urls):
    return FakeResponse(200, {"results": [{"url": u, "title": "T", engine_field: "c"} for u in urls]})


def test_searxng_answers_so_tavily_is_never_paid(monkeypatch, ddgs_results):
    net = FakeNet(monkeypatch, searxng=[hits("content", "https://free.example")], tavily=[])
    results = Searcher(base_url="http://searx.local", tavily_key="tvly-test").search("q")
    assert [r.engine for r in results] == ["searxng"]
    assert net.tavily_calls == [] and ddgs_results == []


def test_searxng_down_uses_tavily_with_basic_one_credit_search(monkeypatch, ddgs_results):
    net = FakeNet(monkeypatch, searxng=[FakeResponse(500)], tavily=[hits("content", "https://paid.example")])
    searcher = Searcher(base_url="http://searx.local", tavily_key="tvly-test")
    results = searcher.search("cyclone")
    assert [(r.url, r.engine) for r in results] == [("https://paid.example", "tavily")]
    [call] = net.tavily_calls
    assert call["url"] == "https://api.tavily.com/search"
    assert call["headers"] == {"Authorization": "Bearer tvly-test"}
    assert call["json"]["search_depth"] == "basic" and call["json"]["query"] == "cyclone"
    assert searcher.tavily_calls == 1 and searcher.searxng_ok is False


def test_searxng_empty_for_one_query_tries_tavily_but_stays_on(monkeypatch, ddgs_results):
    net = FakeNet(monkeypatch, searxng=[FakeResponse(200, {"results": []}), hits("content", "https://free.example")],
                  tavily=[hits("content", "https://paid.example")])
    searcher = Searcher(base_url="http://searx.local", tavily_key="tvly-test")
    assert searcher.search("rare query")[0].engine == "tavily"
    assert searcher.search("common query")[0].engine == "searxng"  # SearXNG was not switched off
    assert len(net.tavily_calls) == 1


@pytest.mark.parametrize("status", [401, 432, 433])
def test_bad_key_or_spent_credits_switch_tavily_off(monkeypatch, ddgs_results, caplog, status):
    net = FakeNet(monkeypatch, searxng=[], tavily=[FakeResponse(status)])
    searcher = Searcher(base_url="", tavily_key="tvly-test")
    assert searcher.search("one")[0].engine == "ddgs"
    assert searcher.search("two")[0].engine == "ddgs"
    assert len(net.tavily_calls) == 1  # never asked again this run
    assert str(status) in caplog.text and "Skipping Tavily" in caplog.text


def test_tavily_rate_limit_skips_only_that_query(monkeypatch, ddgs_results):
    net = FakeNet(monkeypatch, searxng=[], tavily=[FakeResponse(429), hits("content", "https://paid.example")])
    searcher = Searcher(base_url="", tavily_key="tvly-test")
    assert searcher.search("one")[0].engine == "ddgs"
    assert searcher.search("two")[0].engine == "tavily"  # still on for the next query
    assert len(net.tavily_calls) == 2


def test_no_tavily_key_goes_straight_to_ddgs(monkeypatch, ddgs_results):
    net = FakeNet(monkeypatch, searxng=[FakeResponse(500)], tavily=[])
    assert Searcher(base_url="http://searx.local").search("q")[0].engine == "ddgs"
    assert net.tavily_calls == []


def test_cached_query_is_not_paid_twice(monkeypatch, ddgs_results, tmp_path):
    net = FakeNet(monkeypatch, searxng=[], tavily=[hits("content", "https://paid.example")])
    Searcher(base_url="", tavily_key="tvly-test", cache_dir=tmp_path).search("q")
    second = Searcher(base_url="", tavily_key="tvly-test", cache_dir=tmp_path)
    assert second.search("q")[0].engine == "tavily"
    assert len(net.tavily_calls) == 1 and second.tavily_calls == 0

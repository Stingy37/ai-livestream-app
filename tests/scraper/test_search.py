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

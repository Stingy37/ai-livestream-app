"""Offline tests for search: SearXNG and ddgs are both faked."""

import httpx
import pytest

from scraper.search import Searcher, SearchResult


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
            return [{"href": "https://bing.example/a", "title": "A", "body": "b"}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    results = Searcher(base_url="").search("q")
    assert tried == ["auto", "bing, yahoo"]
    assert [r.url for r in results] == ["https://bing.example/a"]

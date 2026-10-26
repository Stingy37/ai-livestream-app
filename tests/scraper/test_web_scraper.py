"""Offline tests for WebScraper.gather: the fetcher and the agent are fakes."""

import pytest

import scraper.agent
import scraper.fetch
from contracts import Scene, ScrapedDocument
from scraper import WebScraper


def scene(sources):
    return Scene(id="s1", node_key="n1", title="Typhoon Marisol", topic_description="landfall",
                 system_instructions="", sources=sources, language="en", script_model="m", tts_model="t", tts_voice="v")


class FakeFetcher:
    instances = []

    def __init__(self, max_threads=8):
        self.max_threads = max_threads
        self.urls = None
        self.client = type("Client", (), {"close": lambda self: None})()
        FakeFetcher.instances.append(self)

    def fetch_all(self, urls):
        self.urls = list(urls)
        return [ScrapedDocument(url=u, title=u, main_text="text", source_name="X") for u in urls if "bad" not in u]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    FakeFetcher.instances = []
    monkeypatch.setattr(scraper.fetch, "Fetcher", FakeFetcher)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)


def test_user_sources_are_fetched_without_discovery(monkeypatch):
    def no_agent(*a, **k):
        raise AssertionError("discovery must not run when sources are given")

    monkeypatch.setattr(scraper.agent, "DiscoveryAgent", no_agent)
    docs = WebScraper(max_threads=3).gather(scene(["https://a.example/1", "https://bad.example/2", "https://c.example/3"]))
    assert [d.url for d in docs] == ["https://a.example/1", "https://c.example/3"]
    assert docs[0].metadata == {"discovered_via": "user"}
    assert FakeFetcher.instances[0].max_threads == 3


def test_empty_sources_run_the_agent(monkeypatch):
    monkeypatch.delenv("LUMEN_API_KEY", raising=False)
    seen = {}

    class FakeAgent:
        def __init__(self, searcher, fetcher, llm):
            seen["llm"] = llm

        def run(self, s):
            return [ScrapedDocument(url="https://found.example", title="t", main_text="x", source_name="F")]

    monkeypatch.setattr(scraper.agent, "DiscoveryAgent", FakeAgent)
    docs = WebScraper().gather(scene([]))
    assert [d.url for d in docs] == ["https://found.example"]
    assert seen["llm"] is None  # no key, so no LLM


def test_unexpected_error_returns_empty_list(monkeypatch):
    class BrokenAgent:
        def __init__(self, *a):
            pass

        def run(self, s):
            raise ValueError("boom")

    monkeypatch.setattr(scraper.agent, "DiscoveryAgent", BrokenAgent)
    assert WebScraper().gather(scene([])) == []

"""Offline tests for the discovery agent: search, fetch and the LLM are all fakes."""

from contracts import Scene, ScrapedDocument
from models.llm_api import QuotaError
from scraper import agent as agent_module
from scraper.agent import DiscoveryAgent
from scraper.search import SearchResult

SCENE = Scene(id="s1", node_key="n1", title="Typhoon Marisol", topic_description="landfall and evacuations",
              system_instructions="", sources=[], language="en", script_model="m", tts_model="t", tts_voice="v")


class FakeSearcher:
    """Each query returns three hits whose URLs include the query, so every query finds new pages."""

    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        slug = query.replace(" ", "-")
        return [SearchResult(f"https://news.example/{slug}/{i}", f"{query} {i}", "snippet " * 80, "fake") for i in range(3)]


class FakeFetcher:
    def __init__(self, broken=()):
        self.requested = []
        self.broken = set(broken)

    def fetch_all(self, urls):
        self.requested.extend(urls)
        return [ScrapedDocument(url=u, title=u, main_text="body " * 500, source_name="Fake News")
                for u in urls if u not in self.broken]


class FakeLLM:
    """Plays back scripted JSON answers; an Exception in the script is raised instead."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def ask_json(self, system_prompt, user_text, max_tokens=None):
        self.prompts.append(user_text)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_llm_plans_picks_and_stops_when_enough():
    llm = FakeLLM([
        {"enough": False, "queries": ["marisol landfall"]},
        {"picks": [3, 1]},
        {"enough": True, "queries": []},
    ])
    fetcher = FakeFetcher()
    docs = DiscoveryAgent(FakeSearcher(), fetcher, llm).run(SCENE)
    assert [d.url for d in docs] == ["https://news.example/marisol-landfall/2", "https://news.example/marisol-landfall/0"]
    assert docs[0].metadata["discovered_via"] == "search"
    assert llm.replies == []  # exactly three LLM calls


def test_llm_only_sees_trimmed_text():
    llm = FakeLLM([{"queries": ["q1"]}, {"picks": [1]}, {"enough": True}])
    DiscoveryAgent(FakeSearcher(), FakeFetcher(), llm).run(SCENE)
    select_prompt, judge_prompt = llm.prompts[1], llm.prompts[2]
    assert "snippet " * 30 not in select_prompt  # 640-char snippets cut to 200
    assert "body " * 100 not in judge_prompt  # 2500-char pages cut to 400
    assert len(judge_prompt) < 1000


def test_round_cap_stops_a_planner_that_never_says_enough(monkeypatch):
    monkeypatch.setattr(agent_module, "TARGET_DOCS", 100)
    replies = []
    for r in range(10):
        replies += [{"enough": False, "queries": [f"query {r}"]}, {"picks": [1]}]
    searcher = FakeSearcher()
    docs = DiscoveryAgent(searcher, FakeFetcher(), FakeLLM(replies)).run(SCENE)
    assert searcher.queries == ["query 0", "query 1", "query 2"]  # MAX_ROUNDS
    assert len(docs) == 3


def test_fetch_cap_limits_pages(monkeypatch):
    monkeypatch.setattr(agent_module, "TARGET_DOCS", 100)
    monkeypatch.setattr(agent_module, "MAX_FETCHES", 4)
    replies = []
    for r in range(3):
        replies += [{"queries": [f"a{r}", f"b{r}"]}, {"picks": [1, 2, 3, 4, 5, 6]}]
    fetcher = FakeFetcher()
    DiscoveryAgent(FakeSearcher(), fetcher, FakeLLM(replies)).run(SCENE)
    assert len(fetcher.requested) == 4


def test_without_llm_searches_title_and_uses_search_order():
    searcher, fetcher = FakeSearcher(), FakeFetcher(broken={"https://news.example/Typhoon-Marisol/0"})
    docs = DiscoveryAgent(searcher, fetcher, llm=None).run(SCENE)
    assert searcher.queries[0] == "Typhoon Marisol"
    assert len(searcher.queries) == 2  # one round of fallback queries, then it stops
    assert docs[0].url == "https://news.example/Typhoon-Marisol/1"  # broken page dropped, order kept


def test_quota_error_switches_llm_off(caplog):
    llm = FakeLLM([QuotaError("Lumen coin budget is spent (insufficient_quota). Stopping.")])
    agent = DiscoveryAgent(FakeSearcher(), FakeFetcher(), llm)
    docs = agent.run(SCENE)
    assert agent.llm is None and docs  # carried on and still found pages
    assert len(llm.prompts) == 1  # the spent quota was never asked again
    assert "insufficient_quota" in caplog.text


def test_llm_saying_nothing_is_worth_reading_is_respected():
    llm = FakeLLM([{"queries": ["q"]}, {"picks": []}, {"enough": False, "queries": []}])
    fetcher = FakeFetcher()
    assert DiscoveryAgent(FakeSearcher(), fetcher, llm).run(SCENE) == []
    assert fetcher.requested == []


def test_no_search_results_returns_empty():
    class EmptySearcher:
        def search(self, query):
            return []

    assert DiscoveryAgent(EmptySearcher(), FakeFetcher(), llm=None).run(SCENE) == []

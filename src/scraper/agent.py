"""The discovery agent: one small LangGraph loop that finds pages for a scene.

Used only when a scene lists no ``sources``. Each round:

    plan    the LLM writes a few search queries (and, after round one, says
            whether the pages kept so far are already enough)
    search  run the queries (SearXNG, falling back to ddgs)
    select  the LLM picks which hits are worth reading, best first
    fetch   download + extract those pages on threads (scraper.fetch)

then loops back to ``plan`` until there is enough, or a cap is hit. The caps
below bound the work and the credits: at most MAX_ROUNDS rounds, two LLM calls a
round, MAX_FETCHES page downloads. The LLM only ever sees search snippets and
short excerpts, never whole pages. If the LLM is unavailable (no key, 503,
quota spent) the agent keeps going without it: the scene title becomes the
query and search order becomes the ranking.
"""

from __future__ import annotations

import logging
from typing import TypedDict
from urllib.parse import urlsplit

from contracts import Scene, ScrapedDocument
from scraper.search import SearchResult

log = logging.getLogger(__name__)

MAX_ROUNDS = 3  # search rounds per scene
MAX_FETCHES = 12  # pages downloaded per scene, across all rounds
TARGET_DOCS = 6  # stop once this many usable pages are in hand
QUERIES_PER_ROUND = 3
PICKS_PER_ROUND = 6  # pages chosen for reading each round
SNIPPET_CHARS = 200  # search snippet length the LLM sees
EXCERPT_CHARS = 400  # page excerpt length the LLM sees when judging "enough"
RECURSION_LIMIT = 4 * MAX_ROUNDS + 4  # LangGraph's own step cap, a backstop under MAX_ROUNDS

PLAN_PROMPT = (
    "You plan web searches that find factual, current source pages for a short live broadcast segment.\n"
    f"Write at most {QUERIES_PER_ROUND} short, specific search-engine queries. Prefer queries that reach "
    "primary sources (official agencies, established news outlets). Do not repeat earlier queries.\n"
    "If pages already found are listed, first decide whether they already cover the topic well enough.\n"
    'Reply in exactly this JSON shape: {"enough": false, "queries": ["..."]}\n'
    "Return ONLY valid JSON."
)
SELECT_PROMPT = (
    "You choose which search results are worth reading for a broadcast segment.\n"
    f"Pick at most {PICKS_PER_ROUND} results that are most likely to contain relevant, factual, current text. "
    "Skip video pages, social media, forums, shops, and duplicates of the same story.\n"
    'Reply in exactly this JSON shape: {"picks": [3, 1, 4]} using the result numbers, best first.\n'
    "Return ONLY valid JSON."
)


class AgentState(TypedDict):
    """Everything the loop knows. Each node returns only the keys it changes."""

    round: int  # rounds started so far
    queries: list[str]  # this round's queries
    past_queries: list[str]
    hits: list[SearchResult]  # this round's new search results
    picks: list[str]  # URLs chosen for reading this round
    seen_urls: list[str]  # every URL already fetched or rejected, so nothing is read twice
    fetches: int  # pages downloaded so far
    documents: list[ScrapedDocument]  # usable pages, best first
    done: bool  # the planner said the pages are enough


class DiscoveryAgent:
    """Finds and fetches pages for one scene. ``searcher``/``fetcher``/``llm`` are injected for tests."""

    def __init__(self, searcher, fetcher, llm=None):
        self.searcher = searcher
        self.fetcher = fetcher
        self.llm = llm  # a models.llm_api.LumenClient, or None to run without the LLM
        self.scene = None

    def run(self, scene: Scene) -> list[ScrapedDocument]:
        from langgraph.graph import END, START, StateGraph

        self.scene = scene
        graph = StateGraph(AgentState)
        graph.add_node("plan", self.plan)
        graph.add_node("search", self.search)
        graph.add_node("select", self.select)
        graph.add_node("fetch", self.fetch)

        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", self.after_plan, ["search", END])
        graph.add_edge("search", "select")
        graph.add_edge("select", "fetch")
        graph.add_conditional_edges("fetch", self.after_fetch, ["plan", END])

        start: AgentState = {
            "round": 0, "queries": [], "past_queries": [], "hits": [], "picks": [],
            "seen_urls": [], "fetches": 0, "documents": [], "done": False,
        }
        final = graph.compile().invoke(start, config={"recursion_limit": RECURSION_LIMIT})
        log.info(
            "agent finished after %d round(s): %d page(s) fetched, %d usable",
            final["round"], final["fetches"], len(final["documents"]),
        )
        return final["documents"]

    # ── nodes ────────────────────────────────────────────────────────────────

    def plan(self, state: AgentState):
        reply = self._ask_json(PLAN_PROMPT, self._plan_request(state))
        if reply is not None:
            done = bool(reply.get("enough")) and bool(state["documents"])
            queries = [q.strip() for q in reply.get("queries", []) if isinstance(q, str) and q.strip()]
        else:  # no LLM: search the title, then the title with the topic, then give up
            done = False
            queries = [self.scene.title, f"{self.scene.title} {self.scene.topic_description}"[:200]]
        queries = [q for q in dict.fromkeys(queries) if q not in state["past_queries"]][:QUERIES_PER_ROUND]
        if done:
            log.info("planner: the pages found so far are enough")
        elif not queries:
            log.info("planner: no new queries left to try")
        else:
            log.info("round %d queries: %s", state["round"] + 1, queries)
        return {
            "round": state["round"] + 1,
            "queries": queries,
            "past_queries": state["past_queries"] + queries,
            "done": done or not queries,
        }

    def search(self, state: AgentState):
        seen = set(state["seen_urls"])
        hits = []
        for query in state["queries"]:
            for hit in self.searcher.search(query):
                if hit.url not in seen:
                    seen.add(hit.url)
                    hits.append(hit)
        log.info("search: %d new result(s)", len(hits))
        return {"hits": hits}

    def select(self, state: AgentState):
        hits = state["hits"]
        budget = min(PICKS_PER_ROUND, MAX_FETCHES - state["fetches"])
        if not hits or budget <= 0:
            return {"picks": []}
        reply = self._ask_json(SELECT_PROMPT, self._select_request(hits))
        if reply is None:  # no LLM answer: trust the search engine's order
            order = list(range(len(hits)))
        else:  # the LLM may also say that nothing here is worth reading
            order = []
            for n in reply.get("picks", []):
                if isinstance(n, int) and 1 <= n <= len(hits) and n - 1 not in order:
                    order.append(n - 1)
        return {"picks": [hits[i].url for i in order[:budget]]}

    def fetch(self, state: AgentState):
        documents = self.fetcher.fetch_all(state["picks"]) if state["picks"] else []
        for document in documents:
            document.metadata.setdefault("discovered_via", "search")
        return {
            "documents": state["documents"] + documents,
            "fetches": state["fetches"] + len(state["picks"]),
            "seen_urls": state["seen_urls"] + [h.url for h in state["hits"]],
        }

    # ── routing (conditional edges) ──────────────────────────────────────────

    def after_plan(self, state: AgentState):
        from langgraph.graph import END

        return END if state["done"] else "search"

    def after_fetch(self, state: AgentState):
        from langgraph.graph import END

        if len(state["documents"]) >= TARGET_DOCS:
            return END
        if state["round"] >= MAX_ROUNDS or state["fetches"] >= MAX_FETCHES:
            log.info("agent stopping: hit its round/page cap")
            return END
        return "plan"

    # ── LLM helpers ──────────────────────────────────────────────────────────

    def _ask_json(self, system_prompt, user_text):
        """The LLM's JSON answer, or None if there is no LLM or it failed (then the agent carries on without it)."""
        if self.llm is None:
            return None
        from models.llm_api import QuotaError

        try:
            return self.llm.ask_json(system_prompt, user_text, max_tokens=400)
        except QuotaError as error:
            log.warning("%s Continuing without the LLM for this scene.", error)
            self.llm = None  # never retry a spent quota
        except Exception as error:
            log.warning("LLM call failed (%s); continuing without it for this step.", error)
        return None

    def _plan_request(self, state: AgentState):
        lines = [
            f"Segment title: {self.scene.title}",
            f"Topic: {self.scene.topic_description}",
            f"Broadcast language: {self.scene.language}",
        ]
        if state["past_queries"]:
            lines.append("Earlier queries: " + "; ".join(state["past_queries"]))
        if state["documents"]:
            lines.append("Pages found so far (title, site, opening text):")
            for d in state["documents"]:
                excerpt = " ".join(d.main_text[:EXCERPT_CHARS].split())
                lines.append(f"- {d.title} ({d.source_name}): {excerpt}")
        return "\n".join(lines)

    def _select_request(self, hits):
        lines = [f"Segment title: {self.scene.title}", f"Topic: {self.scene.topic_description}", "Results:"]
        for n, hit in enumerate(hits, 1):
            snippet = " ".join(hit.snippet[:SNIPPET_CHARS].split())
            lines.append(f"{n}. {hit.title} [{urlsplit(hit.url).netloc}] {snippet}")
        return "\n".join(lines)

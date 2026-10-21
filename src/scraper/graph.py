"""The scraper's LangGraph (internal to the Web Scraper team): search -> verify -> (experts -> search) ...

    seed ──> search ──> verify ──┬──> END          baseline passed, nothing left to try, or 3 rounds used
                 ^               └──> experts ──┘  baseline failed: experts tell the search node what to look for

The search node is a ReAct loop: the model writes a Thought and an Action (search queries and/or
links to follow), the tool layer runs them, and the model is asked whether the gathered information
is sufficient; that repeats up to ``react_max_rounds`` times per visit. Every visit of the search
node is one graph round; after ``max_rounds`` (3) visits the graph ends whatever the verdict.

Runs local-only: no checkpointer, no LangSmith tracing (``LANGCHAIN_TRACING_V2`` is forced off).
All model calls go through ``models.lumen`` (key pool with rotation, local vLLM fallback).
"""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict
from urllib.parse import urlparse

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from langgraph.graph import END, START, StateGraph

from contracts import ScrapedDocument

from scraper.experts import docs_digest, run_experts
from scraper.fetch import FetchResult, Fetcher, to_document
from scraper.prompts import PLAN_SYSTEM, PLAN_USER, SUFFICIENT_SYSTEM, SUFFICIENT_USER, as_str_list, extract_json
from scraper.searx import SearxClient, usable_url
from scraper.verify import (BaselineRule, VerifyResult, baseline, derive_checklist, verify_documents)

log = logging.getLogger(__name__)

MAX_ROUNDS = int(os.environ.get("REACT_MAX_ROUNDS", "3"))            # visits of the search node (graph rounds)
REACT_INNER_ROUNDS = int(os.environ.get("SCRAPE_REACT_INNER_ROUNDS", "2"))   # plan/fetch/sufficient loops per visit
MAX_PAGES = int(os.environ.get("SCRAPE_MAX_PAGES", "14"))
MAX_PER_HOST = int(os.environ.get("SCRAPE_MAX_PER_HOST", "5"))         # discovered pages kept per site (user sources exempt)
MAX_QUERIES = int(os.environ.get("SCRAPE_MAX_QUERIES", "3"))
MAX_FOLLOW = int(os.environ.get("SCRAPE_MAX_FOLLOW", "3"))
RESULTS_PER_QUERY = int(os.environ.get("SCRAPE_FETCH_PER_QUERY", "4"))   # top hits fetched per query
SUFFICIENT_DOC_CAP = int(os.environ.get("SCRAPE_SUFFICIENT_DOC_CHARS", "1500"))
LLM_TOTAL_CAP = int(os.environ.get("SCRAPE_LLM_TOTAL_CHARS", "14000"))
LINK_KEYWORDS = ("typhoon", "cyclone", "bulletin", "advisory", "warning", "signal", "champi", "rosal", "weather",
                 "storm", "surge", "rainfall", "forecast", "evacu", "suspension", "class")
OFFICIAL_BONUS = {"JMA", "JTWC", "PAGASA", "CWA", "HKO", "NHC", "NWS", "NOAA", "KMA", "NDRRMC", "NCHMF"}

AskFn = Callable[[str, str], str]


class ScrapeState(TypedDict, total=False):
    scene: dict[str, Any]            # id, node_key, title, topic, sources, language
    web_search: bool
    round: int                       # visits of the search node so far
    max_rounds: int
    docs: list[ScrapedDocument]      # current pool (ranked, capped)
    urls_done: set[str]              # fetched (ok or not) -> never fetched again this scene
    queries_done: list[str]
    links: dict[str, list[str]]      # page url -> same-domain links (for do_web_search=false expansion)
    fetch_log: list[dict[str, Any]]
    checklist: list[str]
    sufficient: bool
    missing: list[str]
    verify: VerifyResult | None
    baseline: dict[str, Any]
    experts: list[dict[str, Any]]    # one entry per experts visit
    feedback: list[str]              # search suggestions for the next search visit
    trace: list[dict[str, Any]]
    decision: str                    # routing after verify: "experts" | "end"
    new_docs_last_round: int
    end_reason: str


class ScrapeGraph:
    """Builds the graph once; ``run(scene_dict, web_search)`` executes it for one scene."""

    def __init__(self, fetcher: Fetcher, searx: SearxClient | None, ask: AskFn, max_threads: int = 8,
                 max_rounds: int = MAX_ROUNDS, react_inner_rounds: int = REACT_INNER_ROUNDS, max_pages: int = MAX_PAGES,
                 rule: BaselineRule | None = None) -> None:
        self.fetcher = fetcher
        self.searx = searx
        self.ask = ask
        self.max_threads = max_threads
        self.max_rounds = max_rounds
        self.react_inner_rounds = react_inner_rounds
        self.max_pages = max_pages
        self.rule = rule or BaselineRule()
        self.graph = self._build()

    # ---- graph wiring ----------------------------------------------------------------------
    def _build(self):
        g = StateGraph(ScrapeState)
        g.add_node("seed", self.seed_node)
        g.add_node("search", self.search_node)
        g.add_node("verify", self.verify_node)
        g.add_node("experts", self.experts_node)
        g.add_edge(START, "seed")
        g.add_edge("seed", "search")
        g.add_edge("search", "verify")
        g.add_conditional_edges("verify", self.after_verify, {"experts": "experts", "end": END})
        g.add_edge("experts", "search")
        return g.compile()   # no checkpointer: local, in-memory only

    def run(self, scene: dict[str, Any], web_search: bool) -> ScrapeState:
        state: ScrapeState = {"scene": scene, "web_search": web_search, "round": 0, "max_rounds": self.max_rounds,
                              "docs": [], "urls_done": set(), "queries_done": [], "links": {}, "fetch_log": [],
                              "checklist": [], "sufficient": False, "missing": [], "verify": None, "baseline": {},
                              "experts": [], "feedback": [], "trace": [], "decision": "", "end_reason": "", "new_docs_last_round": 0}
        # recursion_limit: seed + 3 x (search, verify, experts) is well under this
        return self.graph.invoke(state, config={"recursion_limit": 40})

    # ---- nodes -----------------------------------------------------------------------------
    def seed_node(self, state: ScrapeState) -> dict[str, Any]:
        """Round 0: fetch the user-supplied sources and derive the coverage checklist."""
        t0 = time.perf_counter()
        scene = state["scene"]
        docs, log_entries = self._fetch_urls(scene.get("sources") or [], state, discovered_by="user_source")
        try:
            checklist = derive_checklist(scene["title"], scene["topic"], self.ask)
        except Exception as exc:  # noqa: BLE001
            log.warning("checklist derivation failed: %s", exc)
            checklist = ["position", "sustained_wind", "movement", "agency_attribution"]
        trace = {"step": "seed", "fetched": [d.url for d in docs], "failed": [e["url"] for e in log_entries if not e["ok"]],
                 "checklist": checklist, "seconds": round(time.perf_counter() - t0, 1)}
        return {"docs": self._rank(docs), "fetch_log": log_entries, "checklist": checklist, "trace": [trace],
                "urls_done": state["urls_done"], "links": state["links"]}

    def search_node(self, state: ScrapeState) -> dict[str, Any]:
        """ReAct: plan -> act (search / follow links) -> observe -> 'is it sufficient?', a few times."""
        t0 = time.perf_counter()
        scene = state["scene"]
        docs = list(state["docs"])
        new_log: list[dict[str, Any]] = []
        queries_done = list(state["queries_done"])
        feedback = list(state.get("feedback") or [])
        inner_trace: list[dict[str, Any]] = []
        sufficient, missing = False, list(state.get("missing") or [])
        round_no = state["round"] + 1
        for inner in range(self.react_inner_rounds):
            can_search = bool(state["web_search"] and self.searx is not None)
            candidates = self._link_candidates(state, docs)
            if not can_search and not candidates:
                inner_trace.append({"inner": inner, "note": "no web search and no links to follow; nothing to do"})
                break
            thought, action = self._plan(scene, docs, feedback + missing, candidates, can_search, queries_done)
            queries = [q for q in action.get("queries", []) if q not in queries_done] if can_search else []
            follow = [u for u in action.get("follow_urls", []) if u in candidates and u not in state["urls_done"]]
            step = {"inner": inner, "thought": thought, "queries": queries, "follow_urls": follow, "fetched": [], "failed": []}
            if not queries and not follow:
                inner_trace.append(step)
                break
            # act: search
            search_urls: list[tuple[str, str]] = []
            if queries:
                time_range = action.get("time_range") if action.get("time_range") in ("day", "week") else None
                with ThreadPoolExecutor(max_workers=min(self.max_threads, len(queries)), thread_name_prefix="searx") as pool:
                    hits_per_query = list(pool.map(lambda q: self.searx.search(q, time_range=time_range), queries))
                for q, hits in zip(queries, hits_per_query):
                    queries_done.append(q)
                    picked = 0
                    for h in hits:
                        if h.url in state["urls_done"] or any(h.url == d.url for d in docs):
                            continue
                        search_urls.append((h.url, q))
                        picked += 1
                        if picked >= RESULTS_PER_QUERY:
                            break
                step["search_hits"] = {q: len(h) for q, h in zip(queries, hits_per_query)}
            fetched_docs, entries = self._fetch_urls([u for u, _ in search_urls], state, discovered_by="search",
                                                     queries={u: q for u, q in search_urls}, round_no=round_no)
            fetched_docs2, entries2 = self._fetch_urls(follow, state, discovered_by="link", round_no=round_no)
            new_docs = fetched_docs + fetched_docs2
            new_log += entries + entries2
            step["fetched"] = [d.url for d in new_docs]
            step["failed"] = [e["url"] for e in entries + entries2 if not e["ok"]]
            docs = self._rank(docs + new_docs)
            # observe: is it enough?
            sufficient, missing, covered = self._sufficient(scene, docs)
            step.update({"sufficient": sufficient, "missing": missing, "covered": covered, "docs": len(docs)})
            inner_trace.append(step)
            feedback = []   # expert feedback is consumed by the first inner round
            if sufficient:
                break
        new_count = sum(1 for d in docs if d.url not in {x.url for x in state["docs"]})
        trace = {"step": "search", "round": round_no, "react": inner_trace, "docs": len(docs), "new_docs": new_count,
                 "seconds": round(time.perf_counter() - t0, 1)}
        return {"docs": docs, "fetch_log": state["fetch_log"] + new_log, "queries_done": queries_done, "round": round_no,
                "sufficient": sufficient, "missing": missing, "feedback": [], "trace": state["trace"] + [trace],
                "urls_done": state["urls_done"], "links": state["links"], "new_docs_last_round": new_count}

    def verify_node(self, state: ScrapeState) -> dict[str, Any]:
        t0 = time.perf_counter()
        docs = state["docs"]
        result = verify_documents(docs, self.ask, previous=state.get("verify"), max_threads=self.max_threads)
        for d in docs:
            d.metadata["verify"] = result.flags_for(d.url)
        gate = baseline(state["checklist"], docs, result, self.rule)
        decision, reason = self._decide(state, gate)
        trace = {"step": "verify", "round": state["round"], "claims": len(result.claims), "dropped_claims": result.dropped_claims,
                 "conflicts": len(result.conflicts), "stale_docs": gate["stale_docs"], "baseline": gate, "next": decision,
                 "seconds": round(time.perf_counter() - t0, 1)}
        return {"verify": result, "baseline": gate, "trace": state["trace"] + [trace], "decision": decision,
                "end_reason": reason if decision == "end" else ""}

    def experts_node(self, state: ScrapeState) -> dict[str, Any]:
        t0 = time.perf_counter()
        scene, gate, verify = state["scene"], state["baseline"], state["verify"]
        flags = [f"{c['quantity_type']}: {c['a']['agency']} vs {c['b']['agency']} ({c['reason']})" for c in (verify.conflicts if verify else [])]
        flags += [f"stale: {url} ({v['reason']})" for url, v in (verify.stale_docs.items() if verify else []) if v["stale"]]
        out = run_experts(state["docs"], scene["title"], scene["topic"], _now_iso(), state["checklist"], gate.get("missing", []),
                          flags, self.ask, max_threads=self.max_threads)
        suggestions = [s for s in out["search_suggestions"] if s not in state["queries_done"]]
        trace = {"step": "experts", "round": state["round"], "search_suggestions": suggestions,
                 "seconds": round(time.perf_counter() - t0, 1)}
        return {"experts": state["experts"] + [{"round": state["round"], **out["experts"]}], "feedback": suggestions,
                "trace": state["trace"] + [trace]}

    # ---- routing ---------------------------------------------------------------------------
    def after_verify(self, state: ScrapeState) -> str:
        return state.get("decision") or "end"

    def _decide(self, state: ScrapeState, gate: dict[str, Any]) -> tuple[str, str]:
        """('experts' | 'end', reason) after a verify pass."""
        if gate.get("passed"):
            return "end", "baseline passed"
        if state["round"] >= state["max_rounds"]:
            return "end", f"{state['max_rounds']} rounds used"
        if state["round"] >= 2 and not state.get("new_docs_last_round"):
            return "end", "last search round found nothing new"
        can_expand = bool(state["web_search"] and self.searx is not None) or bool(self._link_candidates(state, state["docs"]))
        if not can_expand:
            return "end", "baseline failed but nothing more can be fetched (no web search, no links)"
        return "experts", ""

    # ---- tool layer ------------------------------------------------------------------------
    def _fetch_urls(self, urls: list[str], state: ScrapeState, discovered_by: str, queries: dict[str, str] | None = None,
                    round_no: int = 0) -> tuple[list[ScrapedDocument], list[dict[str, Any]]]:
        urls = [u for u in dict.fromkeys(urls) if u and u not in state["urls_done"]]
        if not urls:
            return [], []
        results: list[FetchResult] = self.fetcher.fetch_many(urls)
        docs, entries = [], []
        for r in results:
            state["urls_done"].add(r.url)
            entries.append({"url": r.url, "ok": r.ok, "status": r.status, "error": r.error, "chars": len(r.text),
                            "discovered_by": discovered_by, "cache_hit": r.cache_hit, "round": round_no})
            if r.ok:
                docs.append(to_document(r, discovered_by, (queries or {}).get(r.url, ""), round_no))
                if r.links:
                    state["links"][r.url] = r.links
            else:
                log.warning("dropped %s (%s)", r.url, r.error)
        return docs, entries

    def _link_candidates(self, state: ScrapeState, docs: list[ScrapedDocument]) -> list[str]:
        """Same-domain links on user-supplied pages that look relevant and were not fetched yet."""
        user_urls = set(state["scene"].get("sources") or [])
        out = []
        for page, links in state["links"].items():
            if page not in user_urls:
                continue
            for u in links:
                low = u.lower()
                if u in state["urls_done"] or not usable_url(u) or not any(k in low for k in LINK_KEYWORDS):
                    continue
                out.append(u)
        return list(dict.fromkeys(out))[:25]

    def _rank(self, docs: list[ScrapedDocument]) -> list[ScrapedDocument]:
        """User sources first (config order), then official agencies, then by recency; capped at max_pages."""
        seen, unique = set(), []
        for d in docs:
            if d.url not in seen:
                seen.add(d.url)
                unique.append(d)

        def key(d: ScrapedDocument):
            user = 0 if d.metadata.get("discovered_by") == "user_source" else 1
            official = 0 if d.source_name in OFFICIAL_BONUS else 1
            ts = d.published_at.timestamp() if d.published_at else 0.0
            return (user, official, -ts, d.metadata.get("round", 0))

        ranked, per_host, out = sorted(unique, key=key), {}, []
        for d in ranked:
            host = (urlparse(d.url).hostname or "").lower()
            user = d.metadata.get("discovered_by") == "user_source"
            if not user and per_host.get(host, 0) >= MAX_PER_HOST:
                continue   # keep the pool diverse: one site cannot crowd out the others
            per_host[host] = per_host.get(host, 0) + 1
            out.append(d)
        return out[: self.max_pages]

    # ---- model calls -----------------------------------------------------------------------
    def _plan(self, scene: dict[str, Any], docs: list[ScrapedDocument], feedback: list[str], candidates: list[str],
              can_search: bool, queries_done: list[str]) -> tuple[str, dict[str, Any]]:
        gathered = "\n".join(f"- [{d.source_name}] {d.title[:90]} ({d.published_at.isoformat() if d.published_at else 'no date'}, "
                             f"{len(d.main_text)} chars): {d.main_text[:220].replace(chr(10), ' ')}" for d in docs) or "(nothing yet)"
        fb = "\n".join(f"- {f}" for f in feedback) or "(none)"
        if queries_done:
            fb += "\nQueries already used (do not repeat): " + "; ".join(queries_done[-8:])
        links = "\n".join(f"- {u}" for u in candidates) or "(none)"
        user = PLAN_USER.format(title=scene["title"], topic=scene["topic"], now=_now_iso(), web_search="yes" if can_search else "no",
                                n_docs=len(docs), gathered=gathered[:LLM_TOTAL_CAP], feedback=fb, links=links,
                                max_queries=MAX_QUERIES, max_links=MAX_FOLLOW)
        reply = self.ask(PLAN_SYSTEM, user)
        thought = _thought_of(reply)
        data = extract_json(reply)
        action = data if isinstance(data, dict) else {}
        queries = as_str_list(action.get("queries"), MAX_QUERIES)
        follow = [u for u in as_str_list(action.get("follow_urls"), MAX_FOLLOW) if usable_url(u)]
        return thought, {"queries": queries, "follow_urls": follow, "time_range": action.get("time_range")}

    def _sufficient(self, scene: dict[str, Any], docs: list[ScrapedDocument]) -> tuple[bool, list[str], list[str]]:
        digest = docs_digest(docs, SUFFICIENT_DOC_CAP, LLM_TOTAL_CAP)
        reply = self.ask(SUFFICIENT_SYSTEM, SUFFICIENT_USER.format(title=scene["title"], topic=scene["topic"], now=_now_iso(),
                                                                   cap=SUFFICIENT_DOC_CAP, docs=digest))
        data = extract_json(reply)
        if not isinstance(data, dict):
            return False, ["model reply unreadable"], []
        return bool(data.get("sufficient")), as_str_list(data.get("missing"), 10), as_str_list(data.get("covered"), 10)


_THOUGHT_RE = re.compile(r"Thought:\s*(.+?)(?:\n\s*Action:|\n\s*\{|$)", re.DOTALL | re.IGNORECASE)


def _thought_of(reply: str) -> str:
    m = _THOUGHT_RE.search(reply or "")
    return (m.group(1).strip() if m else (reply or "").strip()[:300])[:400]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

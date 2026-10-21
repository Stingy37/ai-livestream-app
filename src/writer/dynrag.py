"""Dynamic RAG generation, applied exactly the way grpo-rl-usal trained it (src/engine/rollout.py there).

    prompt<think>\n | reasoning <search> q </search> | \n\n<information>Doc 1(..)..</information>\n\n | reasoning </think> | \n\n<answer> a </answer>
                    |------- generated ---------------|------------- inserted --------------------------|-- generated -----|---- generated --------|
                    <-------------------- thinking: THINK_FRACTION x MAX_TOKENS ------------------------------------------> <-- answer: the rest -->

Qwen3's native thinking block is the reasoning channel: the prompt (Search-R1's instruction in one
user message) ends with a forced-open "<think>\\n"; generation stops at </search> (retrieve and
continue), </think> (go answer) or </answer>. A search query is embedded with e5 and the top
CONTEXT_TOPK sentences of the scene's index are spliced into the block as
"\\n\\n<information>Doc i(Title: ...) ...</information>\\n\\n" (never counted as generated tokens).
Budgets, not turn caps: the think block (generated + inserted) may use THINK_FRACTION x MAX_TOKENS;
then "\\n</think>\\n\\n" is forced and the rest is for the answer. One <information> block is capped
at MAX_OBS_TOKENS.

One change from training, by request: the block starts with one retrieval already in place, made
with the original scene description as the query (the up-front ``RetrievedContext``), written as
if the model had searched for it, so a script still has source material even if the policy never
searches.

Generation goes through the vLLM OpenAI server (scripts/vllm_start.sh) with ``model=<LORA_NAME>``,
token-id prompts and ``return_token_ids`` so continuations are exact, with the same sampling the
training evaluation used (T 0.6, top-p 0.95, top-k 20).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config_env import Settings
from rag.cluster import ClusterMatch, SentenceClusterIndex

log = logging.getLogger(__name__)

# grpo-rl-usal/src/engine/prompts.py — verbatim
SEARCH_R1_TEMPLATE = (
    "Answer the given question. "
    "Think step by step inside <think> and </think>. "
    "While thinking, whenever you find you lack some knowledge, you can call a search engine by writing "
    "<search> query </search>; the top searched results will be inserted right after it between <information> "
    "and </information>, and you can keep reasoning with them. "
    "You can search as many times as you want. "
    "When no further external knowledge is needed, close your thinking with </think> and directly provide the answer "
    "inside <answer> and </answer>, without detailed illustrations. For example, <answer> Beijing </answer>. "
    "Question: {question}\n"
)
INFORMATION_TEMPLATE = "\n\n<information>{}</information>\n\n"
THINK_OPEN = "<think>\n"
THINK_CLOSE_FORCED = "\n</think>\n\n"
THINK_STOPS = ["</search>", "</think>", "</answer>", "<information>"]   # the last one is an invalid action
INVALID_INFO_NOTE = "<information>Search results are inserted only after a </search> tag; write a <search> query to look something up.</information>"
REPEAT_NOTE = "<information>Same query as before; the results are already shown above.</information>"
MAX_INVALID_ACTIONS = 2
MAX_REPEATED_SEARCHES = 3    # the same query again and again: close the block and answer with what is there
MAX_SEARCHES = 12            # hard caps so one scene cannot spin for minutes
MAX_TURNS = 24
ANSWER_STOPS = ["</answer>"]
MIN_GEN_TOKENS = 16
MIN_INFO_TOKENS = 64
LEN_RESERVE = 2

_SEARCH_RE = re.compile(r"<search>(.*?)</search>", re.DOTALL)
_ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)


def question_text(q: str) -> str:
    q = q.strip()
    return q if q.endswith("?") else q + "?"


def build_messages(question: str) -> list[dict]:
    return [{"role": "user", "content": SEARCH_R1_TEMPLATE.format(question=question_text(question))}]


def encode_prompt(tokenizer, question: str) -> list[int]:
    """Chat-formatted prompt ids with the thinking block forced open (as in training)."""
    msgs = build_messages(question)
    try:
        ids = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, enable_thinking=True)
    except TypeError:
        ids = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True)
    if hasattr(ids, "input_ids") or isinstance(ids, dict):
        ids = ids["input_ids"]
    return list(ids) + tokenizer.encode(THINK_OPEN, add_special_tokens=False)


def last_search_query(text: str) -> str:
    """Query of the last <search> ... </search> in a generated chunk (generation stops at the first
    </search>, so there is one closing tag; the LAST opening tag before it is the real query)."""
    end = text.rfind("</search>")
    if end < 0:
        return ""
    start = text.rfind("<search>", 0, end)
    if start < 0:
        return ""
    q = text[start + len("<search>"):end].strip()
    return q if len(q) <= 600 else ""      # a 'query' that long is not a query


def extract_answer(text: str) -> str | None:
    ms = _ANSWER_RE.findall(text)
    return ms[-1].strip() if ms else None


def format_information(doc_string: str) -> str:
    return INFORMATION_TEMPLATE.format(doc_string.strip())


def format_hits(hits: list[ClusterMatch], titles: dict[int, str], k: int) -> str:
    """Search-R1's 'Doc i(Title: title) text' lines, one per retrieved sentence."""
    lines = []
    for i, m in enumerate(hits[:k]):
        s = m.sentence
        when = s.published_at.strftime("%Y-%m-%d %H:%M UTC") if s.published_at else "time not reported"
        title = titles.get(s.document_index, s.source_url)
        lines.append(f"Doc {i + 1}(Title: {s.source_name} - {title} [{when}]) {s.text}\n")
    return "".join(lines)


@dataclass
class Trajectory:
    question: str
    prompt_ids: list[int]
    response_ids: list[int] = field(default_factory=list)
    response_mask: list[int] = field(default_factory=list)      # 1 generated, 0 inserted
    text: str = ""
    phase: str = "think"                                        # think | answer | done
    n_turns: int = 0
    n_searches: int = 0
    searches: list[str] = field(default_factory=list)
    retrieved: list[list[dict[str, Any]]] = field(default_factory=list)
    think_tokens: int = 0
    think_closed: str = ""                                      # model | budget | eos
    answer_tokens: int = 0
    answer: str | None = None
    finish: str = ""                                            # answer | answer_in_think | no_answer
    done: bool = False
    turns: list[dict[str, Any]] = field(default_factory=list)   # trace for the attempts file
    generate_s: float = 0.0
    retrieval_s: float = 0.0

    def append_generated(self, ids: list[int]) -> None:
        self.response_ids.extend(ids)
        self.response_mask.extend([1] * len(ids))

    def append_inserted(self, ids: list[int]) -> None:
        self.response_ids.extend(ids)
        self.response_mask.extend([0] * len(ids))

    @property
    def full_ids(self) -> list[int]:
        return self.prompt_ids + self.response_ids

    def summary(self) -> dict[str, Any]:
        return {"finish": self.finish, "n_turns": self.n_turns, "n_searches": self.n_searches, "searches": self.searches,
                "think_tokens": self.think_tokens, "think_closed": self.think_closed, "answer_tokens": self.answer_tokens,
                "n_generated": int(sum(self.response_mask)), "n_response": len(self.response_ids),
                "generate_s": round(self.generate_s, 1), "retrieval_s": round(self.retrieval_s, 2)}


class VLLMCompletions:
    """Minimal client for vLLM's /v1/completions with token-id prompts."""

    def __init__(self, base_url: str, model: str, timeout: float = 900.0) -> None:
        self.url = base_url.rstrip("/") + "/completions"
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def generate(self, ids: list[int], max_tokens: int, stop: list[str], *, temperature: float, top_p: float,
                 top_k: int, seed: int | None) -> dict[str, Any]:
        body = {"model": self.model, "prompt": ids, "max_tokens": int(max_tokens), "temperature": temperature,
                "top_p": top_p, "top_k": top_k, "stop": stop, "include_stop_str_in_output": True,
                "skip_special_tokens": False, "return_token_ids": True}
        if seed is not None:
            body["seed"] = int(seed)
        last: Exception | None = None
        for attempt in range(4):
            try:
                r = self.session.post(self.url, json=body, timeout=self.timeout)
                if r.status_code >= 500:
                    raise RuntimeError(f"vLLM HTTP {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                c = r.json()["choices"][0]
                return {"token_ids": list(c.get("token_ids") or []), "text": c.get("text") or "",
                        "finish_reason": c.get("finish_reason"), "stop_reason": c.get("stop_reason")}
            except (requests.RequestException, RuntimeError, KeyError, ValueError) as error:
                last = error
                log.warning("vLLM request failed (%s); retry %d/3", error, attempt + 1)
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"vLLM unavailable: {last}")


class DynRagGenerator:
    """One scene's generator: tokenizer + sentence index + e5 + vLLM client."""

    def __init__(self, settings: Settings, index: SentenceClusterIndex, tokenizer, encoder=None,
                 client: VLLMCompletions | None = None) -> None:
        self.s = settings
        self.index = index
        self.tok = tokenizer
        self.encoder = encoder
        self.client = client or VLLMCompletions(settings.local_llm_url, settings.lora_name)
        self.eos_ids = set(_eos_ids(tokenizer))
        self.close_ids = tokenizer.encode(THINK_CLOSE_FORCED, add_special_tokens=False)

    # ---- retrieval -------------------------------------------------------------------
    def retrieve(self, query: str) -> list[ClusterMatch]:
        from models.embeddings import get_encoder

        enc = self.encoder or get_encoder()
        return self.index.search_texts([query], top_k=max(self.s.context_topk, self.s.retrieval_top_k), encoder=enc)[0]

    def information_ids(self, hits: list[ClusterMatch], max_tokens: int) -> list[int]:
        wrapper = len(self.tok.encode(format_information(""), add_special_tokens=False))
        docs = format_hits(hits, self.index.titles, self.s.context_topk)
        doc_ids = self.tok.encode(docs.strip(), add_special_tokens=False)
        room = max(max_tokens - wrapper, 8)
        if len(doc_ids) > room:
            docs = self.tok.decode(doc_ids[:room], skip_special_tokens=True)
        return self.tok.encode(format_information(docs), add_special_tokens=False)

    def _drop_tail(self, t: Trajectory, stop: str) -> None:
        """Remove the generated tokens that spell ``stop`` at the end of the response."""
        for n in range(1, 12):
            if n > len(t.response_ids):
                break
            tail = self.tok.decode(t.response_ids[-n:], skip_special_tokens=False)
            if stop in tail:
                del t.response_ids[-n:]
                del t.response_mask[-n:]
                return

    # ---- the rollout ----------------------------------------------------------------
    def generate(self, question: str, initial_query: str | None = None, seed: int | None = None) -> Trajectory:
        s = self.s
        t = Trajectory(question=question, prompt_ids=encode_prompt(self.tok, question))
        budget = min(s.max_tokens, s.local_llm_max_model_len - LEN_RESERVE - len(t.prompt_ids))
        if budget < 512:
            raise ValueError(f"prompt is {len(t.prompt_ids)} tokens; no room to generate (max_model_len {s.local_llm_max_model_len})")
        tb = int(budget * s.think_fraction)
        ab = budget - tb

        def close_think(how: str) -> None:
            t.append_inserted(self.close_ids)
            t.think_closed = how
            t.think_tokens = len(t.response_ids)
            t.phase = "answer"

        # the up-front retrieval, written as the model's own first search
        if initial_query:
            t0 = time.perf_counter()
            hits = self.retrieve(initial_query)
            t.retrieval_s += time.perf_counter() - t0
            if hits:
                head = self.tok.encode(f"<search> {initial_query.strip()} </search>", add_special_tokens=False)
                info = self.information_ids(hits, min(s.max_obs_tokens, tb - len(head) - MIN_GEN_TOKENS))
                t.append_inserted(head + info)
                t.searches.append(initial_query.strip())
                t.retrieved.append([_hit_json(h) for h in hits[:s.context_topk]])
                t.n_searches += 1
                t.turns.append({"kind": "initial_retrieval", "query": initial_query.strip(), "n_hits": len(hits)})

        turn = 0
        invalid = 0
        repeats = 0
        while t.phase == "think":
            if turn >= MAX_TURNS or len(t.searches) >= MAX_SEARCHES or repeats >= MAX_REPEATED_SEARCHES:
                close_think("cap")
                break
            room = min(tb - len(t.response_ids), s.local_llm_max_model_len - LEN_RESERVE - ab - len(t.full_ids))
            if room < MIN_GEN_TOKENS:
                close_think("budget")
                break
            t0 = time.perf_counter()
            o = self.client.generate(t.full_ids, room, THINK_STOPS, temperature=s.gen_temperature, top_p=s.gen_top_p,
                                     top_k=s.gen_top_k, seed=None if seed is None else (seed * 7919 + turn * 104_729) % (2 ** 31 - 1))
            t.generate_s += time.perf_counter() - t0
            t.n_turns += 1
            turn += 1
            t.append_generated(o["token_ids"])
            rec = {"kind": "think", "turn": turn, "stop_reason": o["stop_reason"], "finish_reason": o["finish_reason"],
                   "tokens": len(o["token_ids"]), "text": o["text"][-600:]}
            t.turns.append(rec)
            if o["stop_reason"] == "<information>":
                # the model started writing search results itself: drop that tag and tell it how searching works
                self._drop_tail(t, "<information>")
                invalid += 1
                rec["invalid_information"] = invalid
                if invalid > MAX_INVALID_ACTIONS:
                    close_think("invalid")
                    break
                t.append_inserted(self.tok.encode(format_information(INVALID_INFO_NOTE[len("<information>"):-len("</information>")]), add_special_tokens=False))
            elif o["stop_reason"] == "</search>":
                q = last_search_query(o["text"])
                rec["query"] = q
                if q:
                    room = tb - len(t.response_ids)
                    if room < MIN_INFO_TOKENS:
                        close_think("budget")
                        break
                    if _norm(q) in {_norm(x) for x in t.searches}:
                        # a repeated query gets a one-line note instead of the same block again (saves the budget)
                        t.append_inserted(self.tok.encode(format_information(REPEAT_NOTE[len("<information>"):-len("</information>")]), add_special_tokens=False))
                        t.searches.append(q)
                        repeats += 1
                        rec["repeated"] = True
                    else:
                        t.searches.append(q)
                        t0 = time.perf_counter()
                        hits = self.retrieve(q)
                        t.retrieval_s += time.perf_counter() - t0
                        t.append_inserted(self.information_ids(hits, min(s.max_obs_tokens, room)))
                        t.retrieved.append([_hit_json(h) for h in hits[:s.context_topk]])
                        t.n_searches += 1
                        rec["n_hits"] = len(hits)
                # an empty query inserts nothing; the model just keeps thinking
            elif o["stop_reason"] == "</think>":
                t.think_closed = "model"
                t.think_tokens = len(t.response_ids)
                t.phase = "answer"
            elif o["stop_reason"] == "</answer>":
                t.answer = extract_answer(o["text"])
                t.think_tokens = len(t.response_ids)
                t.finish, t.done, t.phase = "answer_in_think", True, "done"
            elif o["finish_reason"] == "length":
                close_think("budget")
            else:
                if o["token_ids"] and o["token_ids"][-1] in self.eos_ids:
                    del t.response_ids[-1]
                    del t.response_mask[-1]
                close_think("eos")

        if t.phase == "answer":
            room = min(ab, s.local_llm_max_model_len - LEN_RESERVE - len(t.full_ids))
            if room < MIN_GEN_TOKENS:
                t.finish, t.done, t.phase = "no_answer", True, "done"
            else:
                t0 = time.perf_counter()
                o = self.client.generate(t.full_ids, room, ANSWER_STOPS, temperature=s.gen_temperature, top_p=s.gen_top_p,
                                         top_k=s.gen_top_k, seed=None if seed is None else (seed * 7919 + 999_983) % (2 ** 31 - 1))
                t.generate_s += time.perf_counter() - t0
                t.n_turns += 1
                t.append_generated(o["token_ids"])
                t.answer_tokens = len(o["token_ids"])
                t.answer = extract_answer(o["text"])
                if t.answer is None:
                    # the block was opened but never closed (budget): keep what was written after <answer>
                    tail = o["text"].split("<answer>", 1)[1] if "<answer>" in o["text"] else ""
                    t.answer = tail.strip() or None
                t.turns.append({"kind": "answer", "finish_reason": o["finish_reason"], "tokens": len(o["token_ids"]),
                                "text": o["text"][-600:]})
                t.finish = "answer" if t.answer else "no_answer"
                t.done, t.phase = True, "done"
        t.text = self.tok.decode(t.response_ids, skip_special_tokens=False)
        return t


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


def _hit_json(m: ClusterMatch) -> dict[str, Any]:
    s = m.sentence
    return {"text": s.text, "source_name": s.source_name, "source_url": s.source_url, "similarity": round(m.similarity, 4),
            "document_index": s.document_index, "sentence_index": s.sentence_index}


def _eos_ids(tok) -> list[int]:
    ids = []
    if tok.eos_token_id is not None:
        ids.append(tok.eos_token_id)
    for s in ("<|im_end|>", "<|endoftext|>"):
        i = tok.convert_tokens_to_ids(s)
        if isinstance(i, int) and i >= 0 and i != tok.unk_token_id:
            ids.append(i)
    return ids

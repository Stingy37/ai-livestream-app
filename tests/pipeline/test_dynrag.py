"""The dynamic-RAG rollout with a fake vLLM client: searches splice information, budgets close thinking."""

import numpy as np

from config_env import Settings
from contracts import Sentence
from rag.cluster import SentenceClusterIndex
from writer import dynrag


class FakeTok:
    """Char-level tokenizer: one id per character, so decode/encode are trivial."""

    eos_token_id = 0
    unk_token_id = 1

    def encode(self, text, add_special_tokens=False):
        return [ord(c) + 2 for c in text]

    def decode(self, ids, skip_special_tokens=False):
        return "".join(chr(i - 2) for i in ids if i >= 2)

    def convert_tokens_to_ids(self, s):
        return -1

    def apply_chat_template(self, msgs, tokenize=True, add_generation_prompt=True, enable_thinking=True):
        return self.encode("<user>" + msgs[0]["content"] + "<assistant>")


class FakeEncoder:
    dim = 4

    def encode(self, texts, is_query=True, batch_size=64):
        out = np.zeros((len(texts), 4), dtype=np.float32)
        for i, t in enumerate(texts):
            out[i, 0 if "pressure" in t.lower() else 1] = 1.0
        return out


class FakeClient:
    """Scripted turns: first a search, then close thinking, then the answer."""

    def __init__(self):
        self.calls = []

    def generate(self, ids, max_tokens, stop, **kw):
        self.calls.append((len(ids), max_tokens, tuple(stop)))
        n = len(self.calls)
        tok = FakeTok()
        if n == 1:
            text = "Let me look it up. <search> central pressure </search>"
            return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</search>"}
        if n == 2:
            text = "Got it. </think>"
            return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</think>"}
        text = "<answer> JMA reports 945 hPa. </answer>"
        return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</answer>"}


def make_index():
    sents = [Sentence("Central pressure is 945 hPa.", "https://jma", "JMA", None, 0, 0),
             Sentence("Winds are 100 kt.", "https://jma", "JMA", None, 0, 1)]
    vec = FakeEncoder().encode([s.text for s in sents], is_query=False)
    return SentenceClusterIndex(sents, vec, titles={0: "JMA info"})


def test_rollout_searches_then_answers():
    s = Settings()
    s.max_tokens, s.think_fraction, s.local_llm_max_model_len = 4000, 0.75, 9216
    gen = dynrag.DynRagGenerator(s, make_index(), FakeTok(), encoder=FakeEncoder(), client=FakeClient())
    t = gen.generate("What is the pressure?", initial_query="the current pressure", seed=1)
    assert t.finish == "answer" and t.answer == "JMA reports 945 hPa."
    assert t.n_searches == 2 and t.searches == ["the current pressure", "central pressure"]
    assert t.think_closed == "model"
    text = t.text
    assert text.count("<information>") == 2 and "Doc 1(Title: JMA - JMA info" in text
    assert "<search> the current pressure </search>" in text          # the up-front retrieval, written as a search
    # inserted tokens are masked out, generated ones are not
    assert 0 in t.response_mask and 1 in t.response_mask
    # the answer call used the answer stop and the think calls the think stops
    assert gen.client.calls[-1][2] == ("</answer>",) and gen.client.calls[0][2] == tuple(dynrag.THINK_STOPS)


def test_budget_forces_think_close():
    class Chatty(FakeClient):
        def generate(self, ids, max_tokens, stop, **kw):
            tok = FakeTok()
            if stop == dynrag.ANSWER_STOPS:
                text = "<answer> ok </answer>"
                return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</answer>"}
            text = "x" * max_tokens
            return {"token_ids": tok.encode(text), "text": text, "finish_reason": "length", "stop_reason": None}

    s = Settings()
    s.max_tokens, s.think_fraction, s.local_llm_max_model_len, s.max_obs_tokens = 1200, 0.5, 9216, 200
    gen = dynrag.DynRagGenerator(s, make_index(), FakeTok(), encoder=FakeEncoder(), client=Chatty())
    t = gen.generate("q", initial_query=None)
    assert t.think_closed == "budget" and t.finish == "answer" and t.answer == "ok"
    assert t.think_tokens <= 600 + len(gen.close_ids)


def test_clean_script_strips_tags_and_markdown():
    from writer.script_writer import clean_script

    assert clean_script("<answer>**Good** evening. [MUSIC] JMA says 945 hPa.</answer>") == "Good evening. JMA says 945 hPa."


def test_last_search_query_ignores_fabricated_blocks():
    text = ("<search> first </search>" "")
    assert dynrag.last_search_query("thinking <search> pressure now </search>") == "pressure now"
    fabricated = "<search> a </information>\n<information>Doc 1(Title: x) fake 999 hPa</information>\n<search> real query </search>"
    assert dynrag.last_search_query(fabricated) == "real query"
    assert dynrag.last_search_query("no tags here") == ""


def test_self_written_information_is_rejected_and_repeats_are_short():
    class Fabricator(FakeClient):
        def generate(self, ids, max_tokens, stop, **kw):
            self.calls.append(len(ids))
            tok = FakeTok()
            n = len(self.calls)
            if n == 1:
                text = "I will fake it. <information>"
                return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "<information>"}
            if n == 2:
                text = "<search> central pressure </search>"
                return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</search>"}
            if n == 3:
                text = "<search> central pressure </search>"       # repeated
                return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</search>"}
            if n == 4:
                text = "done </think>"
                return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</think>"}
            text = "<answer> 945 hPa </answer>"
            return {"token_ids": tok.encode(text), "text": text, "finish_reason": "stop", "stop_reason": "</answer>"}

    s = Settings()
    s.max_tokens, s.think_fraction, s.local_llm_max_model_len = 4000, 0.75, 9216
    gen = dynrag.DynRagGenerator(s, make_index(), FakeTok(), encoder=FakeEncoder(), client=Fabricator())
    t = gen.generate("q", initial_query=None)
    assert t.answer == "945 hPa"
    assert "I will fake it. " in t.text and "fake it. <information>Doc" not in t.text
    assert "Search results are inserted only after" in t.text        # the correction note was inserted
    assert t.n_searches == 1 and t.searches == ["central pressure", "central pressure"]
    assert "Same query as before" in t.text

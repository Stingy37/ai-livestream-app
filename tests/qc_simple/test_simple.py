"""Offline tests for the simple QC engine: no API calls and no model download."""

import json
from pathlib import Path

from qc.simple.ner import NERExtractor, QuotaError, entity_words
from qc.simple.nli import NLIChecker
from qc.simple.pipeline import QCPipeline

DOCS = Path(__file__).resolve().parents[2] / "fakes" / "qc" / "scraped_documents.json"


def rec(doc, index, text, *entities):
    return {"source_id": doc, "sentence_index": index, "text": text,
            "entities": [{"text": e, "type": "LOCATION"} for e in entities]}


# 1. "Signal No. 3" must stay inside one sentence.
def test_signal_no_stays_in_one_sentence():
    text = "Signal No. 3 was raised over Aurora. Rain is expected."
    assert NERExtractor().split_sentences(text) == ["Signal No. 3 was raised over Aurora.", "Rain is expected."]


# 2. Page cleanup removes clutter from the real messy page and keeps the story.
def test_cleanup_removes_clutter_and_keeps_story():
    doc = next(d for d in json.load(open(DOCS))["documents"] if d["metadata"]["fake_id"] == "doc_03")
    cleaned = QCPipeline(ner=object(), nli=object()).clean_text(doc["main_text"], doc["title"])
    for clutter in ["MENU", "cookie", "Read more", "Share this", "Related articles", "By Staff Reporter"]:
        assert clutter not in cleaned
    assert cleaned.startswith("Typhoon Marisol made landfall in Aurora province")
    assert "\n" not in cleaned  # only the story paragraph is left


# 3. Entity grouping: lowercase and strip, one dictionary of entity -> sentences.
def test_entity_grouping():
    records = [rec("d1", 0, "a", " Luzon "), rec("d2", 0, "b", "LUZON", "Samar")]
    groups = NERExtractor().group_by_entity(records)
    assert len(groups["luzon"]) == 2 and len(groups["samar"]) == 1


# 4. Bad JSON: ask once more, then give up with no entities.
def test_bad_json_retries_once_then_returns_nothing():
    ner = NERExtractor()
    replies = ["not json", "still not json"]
    ner.ask_llm = lambda system, user: replies.pop(0)
    assert ner.extract("x") == []
    assert replies == []  # exactly two attempts were made


def test_bad_json_then_good_json_works():
    ner = NERExtractor()
    replies = ["oops", '```json\n{"entities": [{"text": "Luzon", "type": "LOCATION"}]}\n```']
    ner.ask_llm = lambda system, user: replies.pop(0)
    assert ner.extract("x") == [{"text": "Luzon", "type": "LOCATION"}]


# 5. Label order comes from the model config, never from a fixed index.
def test_label_order_comes_from_id2label():
    import torch

    class Config:
        id2label = {0: "ENTAILMENT", 1: "NEUTRAL", 2: "CONTRADICTION"}  # a different order than usual

    class FakeModel:
        config = Config()

        def __call__(self, **inputs):
            return type("Out", (), {"logits": torch.tensor([[0.0, 0.0, 10.0]])})()

    checker = NLIChecker()
    checker.tokenizer = lambda *a, **k: {}
    checker.model = FakeModel()
    result = checker.check("a", "b")
    assert result["label"] == "contradiction" and result["flagged"] is True


# 6. Both directions are scored and the higher contradiction wins. Below the "sure" level the LLM decides.
def test_both_directions_then_llm_decides():
    asked = []
    checker = NLIChecker(ask_llm=lambda system, user: asked.append(user) or '{"contradiction": true, "reason": "x"}')
    scores = {("a", "b"): {"contradiction": 0.1, "entailment": 0.8, "neutral": 0.1},
              ("b", "a"): {"contradiction": 0.9, "entailment": 0.05, "neutral": 0.05}}
    checker.probabilities = lambda premise, hypothesis: scores[(premise, hypothesis)]
    result = checker.check("a", "b")
    assert result["probabilities"]["contradiction"] == 0.9  # the higher of the two directions
    assert result["flagged"] is True and result["source"] == "llm" and len(asked) == 1
    checker.check("b", "a")  # the same pair in the other order reuses the saved answer
    assert len(asked) == 1


# 6b. A near-certain local contradiction is flagged without paying for the LLM.
def test_sure_local_contradiction_skips_llm():
    checker = NLIChecker(ask_llm=lambda system, user: 1 / 0)  # would crash if it were called
    checker.probabilities = lambda p, h: {"contradiction": 0.995, "entailment": 0.003, "neutral": 0.002}
    result = checker.check("a", "b")
    assert result["flagged"] is True and result["source"] == "nli"


# 6c. The LLM saying "no", or giving a broken answer twice, means not flagged.
def test_llm_no_or_bad_answer_is_not_flagged():
    low = {"contradiction": 0.2, "entailment": 0.4, "neutral": 0.4}
    no = NLIChecker(ask_llm=lambda s, u: '{"contradiction": false, "reason": "different things"}')
    no.probabilities = lambda p, h: low
    assert no.check("a", "b")["flagged"] is False
    broken = NLIChecker(ask_llm=lambda s, u: "not json")
    broken.probabilities = lambda p, h: low
    assert broken.check("a", "b")["flagged"] is False


# 7. Pairs: different documents only, and a pair sharing two entities appears once.
def test_pairs_skip_same_document_and_duplicates():
    records = [rec("d1", 0, "a", "Luzon", "Samar"), rec("d2", 0, "b", "Luzon", "Samar"), rec("d1", 1, "c", "Luzon")]
    pipeline = QCPipeline(ner=NERExtractor(), nli=object())
    pairs = pipeline.build_pairs(pipeline.ner.group_by_entity(records), cross_source=True)
    assert len(pairs) == 2  # (d1#0,d2#0) and (d1#1,d2#0); never d1#0 with d1#1
    assert len(pipeline.build_pairs(pipeline.ner.group_by_entity(records), cross_source=False)) == 1


# 7b. Grouping by entity WORDS: different values of the same kind of thing still meet.
def test_entity_words_let_different_values_meet():
    assert entity_words("130 km/h") == ["km/h"] and entity_words("12,000") == []
    records = [rec("d1", 0, "Winds of 130 km/h.", "130 km/h"), rec("d2", 0, "Winds of 150 km/h.", "150 km/h"),
               rec("d1", 1, "Typhoon Marisol hit Aurora.", "Typhoon Marisol"), rec("d2", 1, "Marisol hit Quezon.", "Marisol")]
    pipeline = QCPipeline(ner=NERExtractor(), nli=object())
    pairs = pipeline.build_pairs(pipeline.ner.group_by_entity(records), cross_source=True)
    assert {(a["text"], b["text"]) for _, a, b in pairs} == {("Winds of 130 km/h.", "Winds of 150 km/h."),
                                                             ("Typhoon Marisol hit Aurora.", "Marisol hit Quezon.")}


# 7c. Two copies of the same sentence are never compared.
def test_identical_sentences_are_skipped():
    records = [rec("d1", 0, "Signal No. 3 is up.", "Signal"), rec("d2", 0, "Signal No. 3 is up.", "Signal")]
    pipeline = QCPipeline(ner=NERExtractor(), nli=object())
    assert pipeline.build_pairs(pipeline.ner.group_by_entity(records), cross_source=True) == []


# 8. Agreement score: 1 - flagged/compared, and None when nothing was compared.
def test_agreement_score():
    compared = [{"a": {"source_id": "d1", "sentence_index": 0}, "b": {"source_id": "d2", "sentence_index": 0}},
                {"a": {"source_id": "d1", "sentence_index": 1}, "b": {"source_id": "d2", "sentence_index": 0}}]
    flagged = [{"sentence_a": {"source_id": "d1", "sentence_index": 0},
                "sentence_b": {"source_id": "d2", "sentence_index": 0}}]
    pipeline = QCPipeline(ner=object(), nli=object())
    flagged = pipeline.blame_minority(flagged)  # only two documents disagree: no majority, both are blamed
    scores = pipeline.agreement_scores(["d1", "d2", "d3"], compared, flagged)
    assert scores == {"d1": 0.5, "d2": 0.0, "d3": None}


# 8b. Majority: d3 disagrees with both d1 and d2, so only d3 is blamed; d1 and d2 keep a perfect score.
def test_blame_goes_to_the_minority_source():
    def s(doc):
        return {"source_id": doc, "sentence_index": 0}

    compared = [{"a": s("d1"), "b": s("d3")}, {"a": s("d2"), "b": s("d3")}, {"a": s("d1"), "b": s("d2")}]
    flagged = [{"sentence_a": s("d1"), "sentence_b": s("d3")}, {"sentence_a": s("d2"), "sentence_b": s("d3")}]
    pipeline = QCPipeline(ner=object(), nli=object())
    flagged = pipeline.blame_minority(flagged)
    assert all(f["blamed"] == [("d3", 0)] for f in flagged)
    assert pipeline.agreement_scores(["d1", "d2", "d3"], compared, flagged) == {"d1": 1.0, "d2": 1.0, "d3": 0.0}


# 8c. Saved answers are tied to the prompt's wording: a changed prompt asks the LLM again.
def test_changed_prompt_is_not_answered_from_the_cache():
    import qc.simple.nli as nli_module

    asked = []
    checker = NLIChecker(ask_llm=lambda system, user: asked.append(system) or '{"contradiction": false, "reason": "x"}')
    checker.ask_judge("a", "b")
    checker.ask_judge("a", "b")
    assert len(asked) == 1  # same prompt: the saved answer is reused
    original = nli_module.JUDGE_PROMPT
    try:
        nli_module.JUDGE_PROMPT = original + " Be strict."
        checker.ask_judge("a", "b")
    finally:
        nli_module.JUDGE_PROMPT = original
    assert len(asked) == 2  # new wording: really asked again


# 9. Running out of coins stops the run with a clear error (no retry).
def test_quota_error_stops():
    class Quota(Exception):
        status_code = 429
        body = {"error": {"code": "insufficient_quota"}}

    class Completions:
        def create(self, **kwargs):
            raise Quota()  # pretend Lumen says the budget is spent

    class Chat:
        completions = Completions()

    class FakeClient:
        chat = Chat()

    ner = NERExtractor()
    ner.client = FakeClient()
    try:
        ner.ask_llm("system prompt", "x")
        assert False, "should have raised"
    except QuotaError:
        pass


# 10. Short documents: the LLM's sentence numbers (counted from 1) become positions (counted from 0).
#     A number that does not exist makes the reply invalid, so it asks once more. The answer is saved.
def test_check_passages_turns_numbers_into_positions():
    replies = ['{"contradictions": [{"a": 9, "b": 1}]}', '{"contradictions": [{"a": 2, "b": 1, "reason": "dates"}]}',
               '{"contradictions": []}']  # the third reply answers the second question
    checker = NLIChecker(ask_llm=lambda system, user: replies.pop(0))
    found = checker.check_passages(["x", "y"], ["z"])
    assert found == [{"a": 1, "b": 0, "reason": "dates"}]
    assert checker.check_passages(["x", "y"], ["z"]) == found and replies == []  # second time: no new call


# 10b. Asking twice: keep everything either question found, without listing the same pair twice.
def test_two_questions_are_combined():
    replies = ['{"contradictions": [{"a": 1, "b": 1, "reason": "first"}]}',
               '{"contradictions": [{"a": 1, "b": 1, "reason": "again"}, {"a": 2, "b": 1, "reason": "new"}]}']
    checker = NLIChecker(ask_llm=lambda system, user: replies.pop(0))
    found = checker.check_passages(["x", "y"], ["z"])
    assert [(f["a"], f["b"]) for f in found] == [(0, 0), (1, 0)]


# 11. The pipeline reads two short documents together and flags the sentences the LLM named.
def test_short_documents_are_read_whole():
    class FakeChecker:
        def check_passages(self, sentences_a, sentences_b):
            return [{"a": 0, "b": 1, "reason": "different years"}]

    records = [rec("d1", 0, "A1"), rec("d1", 1, "A2"), rec("d2", 0, "B1"), rec("d2", 1, "B2")]
    compared, flagged = QCPipeline(ner=object(), nli=FakeChecker()).check_documents(records)
    assert len(compared) == 4 and len(flagged) == 1  # every sentence pair counts as compared
    assert flagged[0]["sentence_a"]["text"] == "A1" and flagged[0]["sentence_b"]["text"] == "B2"

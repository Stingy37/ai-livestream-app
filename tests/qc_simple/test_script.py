"""Offline tests for Part B, the script self contradiction check: no API calls and no model download."""

from contracts import LLMOutput

from qc.simple.ner import NERExtractor
from qc.simple.pipeline import QCPipeline
from qc.simple.script import ScriptChecker


# A NERExtractor that answers from a fixed dictionary instead of the LLM.
def fake_ner(entities_by_sentence):
    saved = [{"text": s, "entities": [{"text": e, "type": "QUANTITY"} for e in es]} for s, es in entities_by_sentence.items()]
    ner = NERExtractor(saved_records=saved)
    ner.ask_llm = lambda system, user: 1 / 0  # would crash if a sentence were missing from the dictionary
    return ner


class FakePassageChecker:
    def __init__(self, found):
        self.found = found
        self.asked = []

    def check_passages(self, sentences_a, sentences_b):
        self.asked.append((sentences_a, sentences_b))
        return self.found


# 1. Speaker labels and stage cues are not spoken, so they are removed before checking.
def test_clean_script_removes_labels_and_cues():
    checker = ScriptChecker(pipeline=QCPipeline(ner=object(), nli=object()))
    text = "ANCHOR: Good evening.\n[RADAR GRAPHIC]\nMaria Santos: Winds are 150 km/h. Stay safe."
    assert checker.clean_script(text) == "Good evening. Winds are 150 km/h. Stay safe."


# 2. A short script is read whole, against itself, and the flagged pair becomes a ScriptScore.
def test_short_script_is_read_whole_against_itself():
    s = ["Winds are 150 km/h.", "Rain is heavy.", "Winds are 120 km/h."]
    nli = FakePassageChecker([{"a": 0, "b": 2, "reason": "different wind speeds"}])
    ner = fake_ner({s[0]: ["150 km/h"], s[2]: ["120 km/h"]})  # sentence 1 is never sent to NER
    result = ScriptChecker(pipeline=QCPipeline(ner=ner, nli=nli)).score(LLMOutput(llm_output=" ".join(s)))
    assert nli.asked == [(s, s)]  # the script is compared with itself
    assert result.total == 1 and result.passes_threshold is False
    assert result.per_entity == {"150 km/h": 1}  # the entity both sentences share a word with
    assert result.contradictions == ['150 km/h: "Winds are 150 km/h." vs "Winds are 120 km/h." (different wind speeds)']


# 3. A clean script scores 0 and passes, without any NER calls.
def test_clean_script_passes():
    ner = fake_ner({})
    result = ScriptChecker(pipeline=QCPipeline(ner=ner, nli=FakePassageChecker([]))).score("All is calm. Rain later.")
    assert result.total == 0 and result.passes_threshold is True and result.contradictions == []


# 4. One sentence can contradict itself; the message says so. With threshold 1, one contradiction still passes.
def test_sentence_that_contradicts_itself():
    s = "It is the first and the second typhoon of the year."
    ner = fake_ner({s: ["typhoon"]})
    nli = FakePassageChecker([{"a": 0, "b": 0, "reason": "first versus second"}])
    result = ScriptChecker(pipeline=QCPipeline(ner=ner, nli=nli), threshold=1).score(s)
    assert result.contradictions == [f'typhoon: "{s}" contradicts itself (first versus second)']
    assert result.passes_threshold is True


# 5. A long script uses Part A's sentence pairs, all inside the script, grouped by entity word.
def test_long_script_uses_sentence_pairs():
    s = ["Winds are 150 km/h.", "Rain is heavy.", "Winds are 120 km/h."]
    ner = fake_ner({s[0]: ["150 km/h"], s[1]: ["rain"], s[2]: ["120 km/h"]})

    class FakeChecker:
        def check(self, a, b):
            return {"label": "contradiction", "probabilities": {"contradiction": 0.995}, "flagged": True,
                    "source": "nli", "reason": ""}

    checker = ScriptChecker(pipeline=QCPipeline(ner=ner, nli=FakeChecker()))
    checker.whole_read_sentences = 2  # make this 3 sentence script count as long
    result = checker.score(" ".join(s))
    assert result.total == 1 and result.per_entity == {"km/h": 1}  # only the two km/h sentences share a word

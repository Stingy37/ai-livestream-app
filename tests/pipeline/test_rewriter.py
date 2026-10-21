"""The last-stage rewriter never passes on a rewrite that adds facts; it falls back to the draft."""

from contracts import LLMOutput, Scene, ScriptOutcome, ScriptScore
from writer.rewriter import ScriptRewriter, new_names, numbers

SCENE = Scene(id="sc-x", node_key="x", title="Current Position", topic_description="Position and intensity of the storm.",
              system_instructions="Neutral anchor. Attribute every claim.", sources=[], language="en",
              script_model="qwen3-8b", tts_model="kokoro", tts_voice="af_heart")
DRAFT = ("JMA reports the storm near 16.0 degrees north with winds of 185 km/h. "
         "JTWC reports 1-minute winds of 240 km/h. The storm is moving west-northwest at 20 km/h.")


def outcome(total=0.0):
    return ScriptOutcome(script=LLMOutput(DRAFT), score=ScriptScore(total=total, passes_threshold=total == 0), accepted=True, attempts=1)


class Scorer:
    def __init__(self, total):
        self.total = total

    def score(self, script, context):
        return ScriptScore(total=self.total, passes_threshold=self.total == 0, contradictions=["x"] * int(self.total))


def rewriter(replies, qc_total=0):
    replies = list(replies)
    return ScriptRewriter(model="m", max_attempts=2, scorer_factory=lambda s: Scorer(qc_total), chat=lambda msgs: replies.pop(0))


GOOD = ("Intensity first: JMA reports winds of 185 km/h, while JTWC, using 1-minute averages, reports 240 km/h. "
        "The storm sits near 16.0 degrees north, moving west-northwest at 20 km/h, so watch how fast it closes in.")


def test_helpers():
    assert numbers("185 km/h, 1,200 people, 16.0N") == {"185", "1200", "16"}
    assert new_names("JMA's update. It heads for Taiwan and the Babuyan Islands.", DRAFT) == ["Taiwan", "Babuyan"]   # place-type words are not names
    assert new_names("JMA's update says so.", DRAFT) == []
    assert new_names("Here, the Joint Typhoon Warning Center disagrees.", DRAFT) == []          # JTWC spelled out
    assert new_names("Here, the Joint Hurricane Center disagrees.", DRAFT) == ["Joint", "Hurricane", "Center"]


def test_good_rewrite_is_used():
    r = rewriter([GOOD]).rewrite(SCENE, outcome())
    assert r.used_rewrite and r.outcome.script.llm_output == GOOD and len(r.attempts) == 1


def test_new_number_is_rejected_then_retried_then_draft_kept():
    bad = GOOD.replace("240 km/h", "250 km/h")
    r = rewriter([bad, bad]).rewrite(SCENE, outcome())
    assert not r.used_rewrite and r.outcome.script.llm_output == DRAFT
    assert "250" in r.attempts[0]["guard_problems"][0]


def test_new_place_rejected_but_second_try_accepted():
    bad = GOOD.replace("closes in.", "closes in on Okinawa.")
    r = rewriter([bad, GOOD]).rewrite(SCENE, outcome())
    assert r.used_rewrite and "Okinawa" in r.attempts[0]["guard_problems"][0]


def test_rewrite_worse_on_qc_is_rejected():
    r = rewriter([GOOD, GOOD], qc_total=2).rewrite(SCENE, outcome(total=0))
    assert not r.used_rewrite and r.outcome.script.llm_output == DRAFT


def test_model_down_keeps_draft():
    def boom(msgs):
        raise RuntimeError("no keys")
    r = ScriptRewriter(model="m", chat=boom, scorer_factory=lambda s: Scorer(0)).rewrite(SCENE, outcome())
    assert not r.used_rewrite and r.reason == "rewrite model unavailable"


def test_new_high_stakes_claim_is_rejected():
    from writer.rewriter import new_terms

    assert new_terms("It may make landfall, a rare event.", "It passes near the islands.") == ["landfall", "rare"]
    assert new_terms("Landfall is expected.", "JMA expects landfall.") == []
    bad = GOOD.replace("so watch how fast it closes in.", "so watch for landfall.")
    r = rewriter([bad, bad]).rewrite(SCENE, outcome())
    assert not r.used_rewrite and "landfall" in r.attempts[0]["guard_problems"][0]


def test_length_targets():
    from writer.length import target_seconds, target_words

    assert target_seconds("Target roughly 220 to 260 seconds (about 4 minutes) of spoken delivery.") == (220, 260)
    assert target_seconds("about 4 minutes") == (216, 264)
    assert target_seconds("Two to three sentences.") is None
    assert target_words("220 to 260 seconds") == (407, 481)


def test_non_english_rewrite_is_checked_on_its_back_translation():
    import dataclasses

    tl = dataclasses.replace(SCENE, language="tl")
    TL = "Ayon sa JMA, ang hangin ay 185 km/h, habang sa JTWC ay 240 km/h. Nasa 16.0 degrees north ito at kumikilos pa-west-northwest sa 20 km/h."
    calls = []

    def chat(msgs):
        calls.append(msgs[0]["content"][:30])
        if msgs[0]["content"].startswith("Translate this"):        # back-translation
            return GOOD.replace("so watch how fast it closes in.", "so watch for landfall.") if "lupa" in msgs[1]["content"] else GOOD
        if msgs[0]["content"].startswith("You translate"):         # plain-translation fallback
            return TL
        return TL + (" Maaaring tumama sa lupa." if len(calls) < 3 else "")

    r = ScriptRewriter(model="m", max_attempts=2, scorer_factory=lambda s: Scorer(0), chat=chat).rewrite(tl, outcome())
    assert r.used_rewrite and r.outcome.script.llm_output.startswith("Ayon sa JMA")
    assert "landfall" in r.attempts[0]["guard_problems"][0]          # the claim was caught through the back-translation


def test_translation_false_positives():
    from writer.rewriter import new_names, new_terms, numbers

    assert numbers("alas 3:45 UTC") <= numbers("at 03:45 UTC")
    assert new_names("Nasa labas ito ng PAR ngayon.", "It is outside the Philippine Area of Responsibility.") == []
    assert new_terms("JMA recorded winds of 185 km/h.", "JMA reports winds of 185 km/h.") == []
    assert new_terms("It was a record-breaking storm.", "It is a strong storm.") == ["record-breaking"]

"""Part B of the simple QC engine: does the live stream script contradict itself?
ScriptChecker uses the same tools as Part A (NERExtractor, NLIChecker, QCPipeline), but on ONE document:
the script is compared with itself, and the result is a ScriptScore (see src/contracts/script.py).

Run:  PYTHONPATH=src python -m qc.simple.script <scripts.json> <output.json> [--judgments judgments.json]
      scripts.json holds {"scripts": [{"id", "text", "contradictions": [{"a", "b"}]}]}, where a and b are
      pieces of the two sentences that really contradict (the answer key, used to report caught and missed).
"""

import argparse
import json
import logging
import os
import re
import time

from contracts import LLMOutput, ScriptScore

from .ner import NERExtractor, entity_words
from .nli import NLIChecker
from .pipeline import QCPipeline

# Scripts up to this many sentences are read whole by the LLM (2 calls). A script often refers back with "it" or
# "the storm", which only a whole read can connect. Longer scripts use Part A's sentence pairs inside the script.
WHOLE_READ_SENTENCES = 25
SCRIPT_ID = "script"
SPEAKER_LABEL = re.compile(r"^\s*[A-Z][A-Za-z .]{0,25}:\s+")  # "ANCHOR: " or "Maria Santos: " at the start of a line
STAGE_CUE = re.compile(r"\[[^\]]*\]")  # "[MUSIC]", "[cut to radar]"


class ScriptChecker:
    # threshold: the most contradictions a script may have and still pass (0 means it must be clean).
    def __init__(self, pipeline=None, threshold=0):
        self.pipeline = pipeline or QCPipeline()
        self.threshold = threshold
        self.whole_read_sentences = WHOLE_READ_SENTENCES

    # Remove what is not spoken: stage cues in square brackets and the speaker label at the start of a line.
    def clean_script(self, text):
        lines = [SPEAKER_LABEL.sub("", STAGE_CUE.sub("", line)).strip() for line in text.split("\n")]
        return " ".join(line for line in lines if line)

    # The entity two flagged sentences argue about: an entity of A that shares a word with an entity of B,
    # else A's first entity. Only flagged sentences go through NER, so a clean script costs no NER calls.
    def name_entity(self, sentence_a, sentence_b):
        entities_a = self.pipeline.ner.extract(sentence_a)
        words_b = {w for e in self.pipeline.ner.extract(sentence_b) for w in entity_words(e["text"])}
        for e in entities_a:
            if words_b & set(entity_words(e["text"])):
                return e["text"]
        return entities_a[0]["text"] if entities_a else "unknown"

    # Short script: the LLM reads it against itself. Same output shape as QCPipeline.check_pairs.
    def check_whole(self, sentences):
        found = self.pipeline.nli.check_passages(sentences, sentences)
        flagged = []
        for item in found:
            a, b = sentences[item["a"]], sentences[item["b"]]
            flagged.append({"entity": self.name_entity(a, b), "sentence_a": {"sentence_index": item["a"], "text": a},
                            "sentence_b": {"sentence_index": item["b"], "text": b}, "reason": item["reason"]})
        return flagged

    # Long script: Part A's method, pairs of sentences that share an entity word, all inside the script.
    def check_long(self, sentences):
        records = self.pipeline.ner.run({SCRIPT_ID: " ".join(sentences)})
        pairs = self.pipeline.build_pairs(self.pipeline.ner.group_by_entity(records), cross_source=False)
        return self.pipeline.check_pairs(pairs)[1]

    # The whole job for one script: the text (or the writer's LLMOutput) in, a ScriptScore out.
    def score(self, script):
        text = script.llm_output if isinstance(script, LLMOutput) else script
        sentences = self.pipeline.ner.split_sentences(self.clean_script(text))
        if len(sentences) <= self.whole_read_sentences:
            flagged = self.check_whole(sentences)
        else:
            flagged = self.check_long(sentences)
        per_entity, messages = {}, []
        for f in flagged:
            per_entity[f["entity"]] = per_entity.get(f["entity"], 0) + 1
            a, b = f["sentence_a"]["text"], f["sentence_b"]["text"]
            if f["sentence_a"]["sentence_index"] == f["sentence_b"]["sentence_index"]:
                messages.append(f'{f["entity"]}: "{a}" contradicts itself ({f["reason"]})')
            else:
                messages.append(f'{f["entity"]}: "{a}" vs "{b}" ({f["reason"]})')
        total = len(flagged)
        return ScriptScore(total=total, per_entity=per_entity, contradictions=messages,
                           passes_threshold=total <= self.threshold)


# Was a labelled contradiction caught? Yes if one message quotes both pieces of the answer key.
def caught(label, messages):
    return any(label["a"] in m and label["b"] in m for m in messages)


def main():
    logging.basicConfig(level=logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scripts_json")
    parser.add_argument("output_json")
    parser.add_argument("--judgments", help="file of saved LLM answers: read if it exists, written after the run")
    args = parser.parse_args()

    judgments = json.load(open(args.judgments, encoding="utf-8")) if args.judgments and os.path.exists(args.judgments) else None
    ner = NERExtractor()
    pipeline = QCPipeline(ner=ner, nli=NLIChecker(ask_llm=ner.ask_llm, judge_model=ner.model, saved_judgments=judgments))
    checker = ScriptChecker(pipeline)
    start, results, hits, labels, extra = time.time(), [], 0, 0, 0
    for item in json.load(open(args.scripts_json, encoding="utf-8"))["scripts"]:
        result = checker.score(item["text"])
        found = [caught(label, result.contradictions) for label in item["contradictions"]]
        matched = [m for m in result.contradictions if any(caught(label, [m]) for label in item["contradictions"])]
        hits, labels, extra = hits + sum(found), labels + len(found), extra + len(result.contradictions) - len(matched)
        print(f"{item['id']}: total {result.total}, caught {sum(found)}/{len(found)}, passes {result.passes_threshold}")
        for message in result.contradictions:
            print("   ", message)
        results.append({"id": item["id"], **result.__dict__})
    if args.judgments:
        json.dump(pipeline.nli.judgments, open(args.judgments, "w", encoding="utf-8"), indent=1)
    json.dump(results, open(args.output_json, "w", encoding="utf-8"), indent=2)
    print(f"caught {hits}/{labels} planted contradictions | other flags (possible false alarms): {extra} | "
          f"NER LLM calls: {ner.calls} | judge LLM calls: {pipeline.nli.llm_calls} | seconds: {time.time() - start:.0f}")


if __name__ == "__main__":
    main()

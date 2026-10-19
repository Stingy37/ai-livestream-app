"""The main class of the simple QC engine: documents in, contradictions and agreement scores out.
QCPipeline cleans the pages, finds entities, compares sentences that share an entity, and scores
each document by how often its sentences were flagged.

Run:  PYTHONPATH=src python -m qc.simple.pipeline <documents.json> <output.json>
      [--limit N] [--reuse saved_ner.json] [--save-ner ner.json] [--within-source] [--judgments judgments.json]
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime
from itertools import combinations, product

from contracts import ScrapedDocument

from .ner import NERExtractor
from .nli import NLIChecker

SHORT_DOC_SENTENCES = 5  # documents this short are read whole by the LLM instead of sentence pair by pair


# Small helpers: a sentence's id, and the part of a record we write to the output file.
def sentence_id(record):
    return (record["source_id"], record["sentence_index"])


def short(record):
    return {k: record[k] for k in ("source_id", "sentence_index", "text")}


class QCPipeline:
    # The NLI checker borrows the NER extractor's LLM connection, so there is only one API client.
    def __init__(self, ner=None, nli=None):
        self.ner = ner or NERExtractor()
        self.nli = nli or NLIChecker(ask_llm=self.ner.ask_llm, judge_model=self.ner.model)

    # Read the fake scraper file into ScrapedDocument objects (dates become datetimes).
    def load_documents(self, path):
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)["documents"]
        for row in rows:
            for field in ("published_at", "fetched_at"):
                row[field] = datetime.fromisoformat(row[field]) if row[field] else None
        return [ScrapedDocument(**row) for row in rows]

    # Remove page clutter line by line (menus, cookie notices, Read more, Share this, repeated
    # headlines, bylines, Related articles lists) and keep the story.
    def clean_text(self, text, title=""):
        kept, in_related = [], False
        for line in text.split("\n"):
            low = line.strip().lower()
            if not low:
                continue
            if low.startswith("related article"):
                in_related = True
                continue
            short_line = len(low) < 80 and not low.endswith(".")
            if in_related and (short_line or low.startswith("-")):
                continue  # still inside the Related articles list
            in_related = False
            menu = line.count("|") >= 2 or low.startswith(("menu ", "skip to content"))
            boilerplate = low.startswith(("read more", "share this")) or ("cookie" in low and len(low) < 200)
            byline = low.startswith("by ") and len(low) < 40
            repeat = short_line and len(low) >= 15 and (low in title.lower() or (kept and low == kept[-1].strip().lower()))
            if not (menu or boilerplate or byline or repeat):
                kept.append(line)
        return "\n".join(kept)

    # Sentence pairs that share an entity. Cross-source: different documents. Otherwise: same document.
    # A pair is never repeated, even if the two sentences share several entities.
    def build_pairs(self, groups, cross_source=True):
        seen, pairs = set(), []
        for entity, sentences in groups.items():
            for a, b in combinations(sentences, 2):
                key = frozenset([sentence_id(a), sentence_id(b)])
                same_doc = a["source_id"] == b["source_id"]
                if len(key) < 2 or key in seen:
                    continue  # a sentence with itself, or a pair we already have
                if a["text"] == b["text"]:
                    continue  # two copies of the same sentence cannot contradict each other
                if cross_source and same_doc:
                    continue  # Part A wants different documents
                if not cross_source and not same_doc:
                    continue  # Part B wants the same document
                seen.add(key)
                pairs.append((entity, a, b))
        return pairs

    # Check every pair (local model first, LLM when needed). Returns (everything compared, only the flagged ones).
    def check_pairs(self, pairs):
        compared, flagged = [], []
        for entity, a, b in pairs:
            result = self.nli.check(a["text"], b["text"])
            p = result["probabilities"]["contradiction"]
            compared.append({"a": short(a), "b": short(b), "contradiction": round(p, 4),
                             "flagged": result["flagged"], "source": result["source"]})
            if result["flagged"]:
                flagged.append({"entity": entity, "sentence_a": short(a), "sentence_b": short(b), "label": result["label"],
                                "confidence": round(p, 4), "source": result["source"], "reason": result["reason"]})
        return compared, flagged

    # Short documents: one LLM call per document pair reads both whole documents and names the contradicting
    # sentences. Every sentence of both documents counts as compared. Part B compares each document with itself.
    def check_documents(self, records, cross_source=True):
        docs = {}
        for record in records:
            docs.setdefault(record["source_id"], []).append(record)
        doc_pairs = list(combinations(docs, 2)) if cross_source else [(d, d) for d in docs]
        compared, flagged = [], []
        for doc_a, doc_b in doc_pairs:
            sents_a, sents_b = docs[doc_a], docs[doc_b]
            found = self.nli.check_passages([r["text"] for r in sents_a], [r["text"] for r in sents_b])
            for a, b in product(sents_a, sents_b):
                compared.append({"a": short(a), "b": short(b), "contradiction": 0.0, "flagged": False, "source": "llm"})
            for item in found:  # a and b can be the same sentence when one sentence contradicts itself
                a, b = sents_a[item["a"]], sents_b[item["b"]]
                flagged.append({"entity": "whole documents", "sentence_a": short(a), "sentence_b": short(b),
                                "label": "contradiction", "confidence": 1.0, "source": "llm", "reason": item["reason"]})
        return compared, flagged

    # Decide who is to blame in each flagged pair: the sentence that disagrees with MORE other documents is the
    # minority claim. A sentence's "opponents" are the other documents that have a sentence flagged against it.
    # Equal counts (for example only two documents) mean there is no majority, so both sentences are blamed.
    def blame_minority(self, flagged):
        opponents = {}  # sentence id -> set of documents that disagree with it
        for f in flagged:
            a, b = sentence_id(f["sentence_a"]), sentence_id(f["sentence_b"])
            opponents.setdefault(a, set()).add(b[0])
            opponents.setdefault(b, set()).add(a[0])
        for f in flagged:
            a, b = sentence_id(f["sentence_a"]), sentence_id(f["sentence_b"])
            blamed = []
            if len(opponents[a]) >= len(opponents[b]):
                blamed.append(a)  # A disagrees with at least as many documents as B does
            if len(opponents[b]) >= len(opponents[a]):
                blamed.append(b)
            f["blamed"] = blamed
        return flagged

    # Agreement per document = 1 - (its blamed sentences / its compared sentences). None if never compared.
    def agreement_scores(self, doc_ids, compared, flagged):
        scores = {}
        for doc in doc_ids:
            seen = {(x["source_id"], x["sentence_index"]) for c in compared for x in (c["a"], c["b"]) if x["source_id"] == doc}
            bad = {tuple(s) for f in flagged for s in f["blamed"] if s[0] == doc}
            scores[doc] = round(1 - len(bad) / len(seen), 3) if seen else None
        return scores

    # The whole job for a list of documents.
    def run(self, documents, cross_source=True):
        passages = {d.metadata["fake_id"]: self.clean_text(d.main_text, d.title) for d in documents}
        records = self.ner.run(passages)
        longest = max([sum(1 for r in records if r["source_id"] == d) for d in passages] or [0])
        if longest <= SHORT_DOC_SENTENCES:
            compared, flagged = self.check_documents(records, cross_source)  # short: read whole documents
        else:
            pairs = self.build_pairs(self.ner.group_by_entity(records), cross_source)  # long: sentence pairs
            compared, flagged = self.check_pairs(pairs)
        flagged = self.blame_minority(flagged)
        scores = self.agreement_scores(list(passages), compared, flagged)
        return {"pairs_compared": len(compared), "flagged_pairs": flagged, "agreement": scores,
                "compared": compared, "records": records}


def main():
    logging.basicConfig(level=logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents_json")
    parser.add_argument("output_json")
    parser.add_argument("--limit", type=int, help="most LLM calls allowed")
    parser.add_argument("--reuse", help="saved NER output, so we do not pay for NER again")
    parser.add_argument("--save-ner", help="write the NER output here")
    parser.add_argument("--within-source", action="store_true", help="compare sentences inside one document")
    parser.add_argument("--judgments", help="file of saved LLM contradiction answers: read if it exists, written after the run")
    args = parser.parse_args()

    saved = json.load(open(args.reuse, encoding="utf-8")) if args.reuse else None
    judgments = json.load(open(args.judgments, encoding="utf-8")) if args.judgments and os.path.exists(args.judgments) else None
    ner = NERExtractor(saved_records=saved, max_calls=args.limit)
    pipeline = QCPipeline(ner=ner, nli=NLIChecker(ask_llm=ner.ask_llm, judge_model=ner.model, saved_judgments=judgments))
    start = time.time()
    result = pipeline.run(pipeline.load_documents(args.documents_json), cross_source=not args.within_source)
    if args.save_ner:
        json.dump(result["records"], open(args.save_ner, "w", encoding="utf-8"), indent=2)
    if args.judgments:
        json.dump(pipeline.nli.judgments, open(args.judgments, "w", encoding="utf-8"), indent=1)
    json.dump({k: v for k, v in result.items() if k != "records"}, open(args.output_json, "w", encoding="utf-8"), indent=2)
    print(f"NER LLM calls: {ner.calls} | judge LLM calls: {pipeline.nli.llm_calls} | pairs compared: {result['pairs_compared']} | "
          f"flagged: {len(result['flagged_pairs'])} | seconds: {time.time() - start:.0f}")
    print("agreement:", result["agreement"])


if __name__ == "__main__":
    main()

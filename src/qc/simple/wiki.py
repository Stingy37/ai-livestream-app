"""Test the simple QC engine on WikiContradict: 506 pairs of Wikipedia passages that contradict.
Mode "nli" scores the given pairs (plus mismatched pairs as a negative control); mode "full" runs
the whole pipeline (NER, entity grouping, NLI) on a random sample of rows, one row at a time.

Run: PYTHONPATH=src python -m qc.simple.wiki nli OUT.json
     PYTHONPATH=src python -m qc.simple.wiki full OUT.json --rows 50 [--reuse NER.json --save-ner NER.json]
"""

import argparse
import json
import logging
import random
from collections import defaultdict

from contracts import ScrapedDocument

from .ner import NERExtractor
from .nli import NLIChecker
from .pipeline import QCPipeline

DATA = "fakes/qc/wikicontradict/train.json"


# Read the saved dataset and keep ONE row per distinct passage pair (many questions share a pair).
def load_rows(path=DATA):
    rows, seen, pairs = json.load(open(path, encoding="utf-8"))["rows"], set(), []
    for row in rows:
        key = frozenset([row["context1"], row["context2"]])
        if key not in seen:
            seen.add(key)
            pairs.append(row)
    return pairs


# Turn one row into two "documents": context1 is source A and context2 is source B.
def row_to_documents(row):
    docs = []
    for n in ("1", "2"):
        docs.append(ScrapedDocument(url=row["url"], title=row["WikipediaArticleTitle"], main_text=row["context" + n],
                                    source_name="wikipedia context" + n,
                                    metadata={"fake_id": f"q{row['question_ID']}_c{n}"}))
    return docs


# Print "flagged x of y" for rows grouped by a column (for example contradictType).
def print_by(results, key, flag):
    groups = defaultdict(list)
    for r in results:
        groups[r[key]].append(r[flag])
    for name, flags in sorted(groups.items()):
        print(f"    {name:<32} {sum(flags):>3} of {len(flags):>3} = {sum(flags) / len(flags):.2f}")


# Mode "nli": score the real pairs, and mismatched pairs from different articles as a negative control.
def nli_mode(rows, checker):
    results = []
    for i, row in enumerate(rows):
        step = len(rows) // 2  # a pair about half a dataset away
        other = rows[(i + step) % len(rows)]
        while other["WikipediaArticleTitle"] == row["WikipediaArticleTitle"]:
            step += 1  # same article: move on to the next pair
            other = rows[(i + step) % len(rows)]
        real = checker.check(row["context1"], row["context2"])
        fake = checker.check(row["context1"], other["context2"])
        results.append({"id": row["question_ID"], "type": row["contradictType"], "same_passage": row["samepassage"],
                        "p_real": round(real["probabilities"]["contradiction"], 4), "flag_real": real["flagged"],
                        "p_mismatched": round(fake["probabilities"]["contradiction"], 4), "flag_mismatched": fake["flagged"]})
    tp, fp = sum(r["flag_real"] for r in results), sum(r["flag_mismatched"] for r in results)
    print(f"REAL contradicting pairs flagged (recall, unit: pairs): {tp} of {len(results)} = {tp / len(results):.2f}")
    print_by(results, "type", "flag_real")
    print_by(results, "same_passage", "flag_real")
    print(f"MISMATCHED pairs flagged (false alarm rate, unit: pairs): {fp} of {len(results)} = {fp / len(results):.2f}")
    print(f"Precision on this 1:1 mix (real vs mismatched): {tp / max(tp + fp, 1):.2f}")
    return results


# Mode "full": run the whole pipeline on each sampled row (two documents) and record what happened.
def full_mode(rows, pipeline, how_many, seed=0):
    results, records = [], []
    try:
        for row in random.Random(seed).sample(rows, how_many):
            out = pipeline.run(row_to_documents(row))
            records.extend(out["records"])
            results.append({"id": row["question_ID"], "type": row["contradictType"], "compared": out["pairs_compared"] > 0,
                            "flagged": len(out["flagged_pairs"]) > 0, "pairs_compared": out["pairs_compared"],
                            "flagged_pairs": out["flagged_pairs"], "agreement": out["agreement"]})
    except Exception as error:  # for example the coin budget ran out: keep what we have
        print("STOPPED EARLY:", type(error).__name__, error)
    n = len(results)
    compared = sum(r["compared"] for r in results)
    flagged = sum(r["flagged"] for r in results)
    print(f"Rows run: {n} | LLM calls: {pipeline.ner.calls}")
    print(f"Rows where the two passages shared an entity and were compared: {compared} of {n}")
    print(f"Rows flagged as contradicting (recall, unit: rows): {flagged} of {n} = {flagged / max(n, 1):.2f}")
    print(f"Flagged, given they were compared: {flagged} of {compared}")
    print_by(results, "type", "flagged")
    return results, records


def main():
    logging.basicConfig(level=logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["nli", "full"])
    parser.add_argument("output_json")
    parser.add_argument("--rows", type=int, default=50)
    parser.add_argument("--reuse", help="saved NER records to reuse")
    parser.add_argument("--save-ner", help="where to write the NER records")
    args = parser.parse_args()

    rows = load_rows()
    if args.mode == "nli":
        results = nli_mode(rows, NLIChecker())
    else:
        saved = json.load(open(args.reuse, encoding="utf-8")) if args.reuse else None
        pipeline = QCPipeline(ner=NERExtractor(saved_records=saved))
        results, records = full_mode(rows, pipeline, args.rows)
        if args.save_ner:
            json.dump(records, open(args.save_ner, "w", encoding="utf-8"), indent=1)
    json.dump(results, open(args.output_json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()

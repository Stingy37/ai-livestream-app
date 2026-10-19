"""Check QC output against the labels file: recall (items), precision (flagged pairs), 8 hardest misses.
Also says whether the doc_09 self-contradiction was caught. Run: python -m qc.simple.evaluate OUT LABELS [WITHIN]
"""

import json
import sys

# Which facts a sentence talks about. These keywords are separate from the pipeline on purpose.
def tags(text):
    t = text.lower()
    found = set()
    if "wind" in t and "km/h" in t:
        found.add("winds")
    if "km/h" in t and any(w in t for w in ("moving", "heading", "crawling", "racing")):
        found.add("motion")
    if any(w in t for w in ("landfall", "ashore", "struck", "slammed", "devastated", " hit ")):
        found.update(["landfall_location", "landfall_date"])
    if "evacuat" in t:
        found.add("evacuees")
    if "signal no" in t:
        found.add("warning_signal")
    if "rainfall" in t or " mm" in t:
        found.add("rainfall")
    return found

# True if the text names `place` but not `other`.
def only(text, place, other):
    return place in text.lower() and other not in text.lower()


# The two documents of a pair, as an unordered set.
def docs_of(a, b):
    return frozenset([a["source_id"], b["source_id"]])


# Read an output file (ours is a dict; an older file is a plain list of flagged pairs).
def load(path):
    data = json.load(open(path, encoding="utf-8"))
    return (data["flagged_pairs"], data.get("compared", [])) if isinstance(data, dict) else (data, [])


def main():
    flagged, compared = load(sys.argv[1])
    labels = json.load(open(sys.argv[2], encoding="utf-8"))
    expected = {e["id"]: {frozenset(p) for p in e["expected_flagged_pairs"]} for e in labels["planted_disagreements"]}
    ambiguous = {frozenset(p) for e in labels["planted_disagreements"] for p in e.get("ambiguous_pairs_not_scored", [])}
    caught, correct, wrong, skipped = set(), 0, [], 0
    for f in flagged:
        a, b = f["sentence_a"], f["sentence_b"]
        pair, shared = docs_of(a, b), tags(a["text"]) & tags(b["text"])
        hits = {fact for fact in shared if pair in expected.get(fact, set())}
        if pair in ambiguous:
            hits.discard("landfall_location")  # doc_09 names two landfall places, so only its location is not scored
        if hits:
            correct += 1
            caught.update((fact, pair) for fact in hits)
        elif pair in ambiguous and "landfall_location" in shared:
            skipped += 1
        else:
            wrong.append(f)

    print("RECALL per fact (unit: expected items = fact + document pair)")
    for fact, pairs in expected.items():
        got = sum(1 for p in pairs if (fact, p) in caught)
        print(f"  {fact:<18} {got:>2} of {len(pairs):>2}  = {got / len(pairs):.2f}")
    total, scored = sum(len(p) for p in expected.values()), correct + len(wrong)
    print(f"  {'ALL':<18} {len(caught):>2} of {total:>2}  = {len(caught) / total:.2f}")
    print(f"PRECISION (unit: flagged sentence pairs): {correct} of {scored} = {correct / max(scored, 1):.2f}"
          f"  ({skipped} ambiguous doc_09 pairs not scored)")

    print("FLAGGED PAIRS NOT IN THE LABELS (review by hand):")
    for f in wrong:
        a, b = f["sentence_a"], f["sentence_b"]
        print(f"  {a['source_id']}#{a['sentence_index']} vs {b['source_id']}#{b['sentence_index']} ({f['entity']}): {a['text'][:55]} | {b['text'][:55]}")

    # Hardest misses: an item never compared is hardest, then the lowest contradiction probability.
    misses = []
    for fact, pairs in expected.items():
        for p in pairs:
            if (fact, p) in caught:
                continue
            probs = [c["contradiction"] for c in compared if docs_of(c["a"], c["b"]) == p
                     and fact in tags(c["a"]["text"]) & tags(c["b"]["text"])]
            misses.append((max(probs) if probs else -1, fact, sorted(p)))
    print("8 HARDEST MISSES (unit: items). 'never compared' means no sentence pair was even tried:")
    for best, fact, p in sorted(misses)[:8]:
        print(f"  {fact:<18} {p}  " + ("never compared" if best < 0 else f"best contradiction prob {best:.2f}"))

    if len(sys.argv) > 3:
        within, _ = load(sys.argv[3])
        hit = False
        for f in within:
            a, b = f["sentence_a"], f["sentence_b"]
            if a["source_id"] == b["source_id"] == "doc_09":  # one sentence says Aurora only, the other Quezon only
                hit = hit or (only(a["text"], "aurora", "quezon") and only(b["text"], "quezon", "aurora"))
                hit = hit or (only(b["text"], "aurora", "quezon") and only(a["text"], "quezon", "aurora"))
        print("doc_09 self-contradiction (Aurora vs Quezon) caught in within-source run:", "YES" if hit else "NO")

if __name__ == "__main__":
    main()

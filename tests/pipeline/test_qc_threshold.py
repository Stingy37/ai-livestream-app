"""The dynamic Part A threshold never removes more than QC_MAX_REMOVED_FRACTION of the pool."""

from contracts import ScrapedDocument
from qc.quality_control import WebsiteScorer


class FakePipeline:
    def __init__(self, agreement):
        self.agreement = agreement

    def run(self, documents, cross_source=True):
        return {"pairs_compared": 10, "flagged_pairs": [], "agreement": self.agreement, "compared": [], "records": []}


class FakeQC:
    def __init__(self, agreement):
        self.pipeline = FakePipeline(agreement)

    def save_caches(self):
        pass

    def stats(self):
        return {}


def docs(n):
    return [ScrapedDocument(url=f"https://x/{i}", title=f"d{i}", main_text="t", source_name="A") for i in range(n)]


def run(monkeypatch, agreement, n, frac=0.15, base=0.6):
    import qc.quality_control as qcmod

    monkeypatch.setattr(qcmod, "SceneQC", lambda scene_dir, settings: FakeQC(agreement))
    scorer = WebsiteScorer(threshold=base, max_removed_fraction=frac)
    return scorer.score_documents(docs(n)), scorer


def test_at_most_15_percent_removed_even_when_everything_is_bad(monkeypatch):
    agreement = {f"doc_{i:02d}": 0.1 for i in range(20)}
    scored, scorer = run(monkeypatch, agreement, 20)
    assert sum(not s.accepted for s in scored) <= 3            # floor(0.15 * 20) = 3
    assert scorer.last_result["effective_threshold"] <= 0.1


def test_good_documents_are_never_removed(monkeypatch):
    agreement = {f"doc_{i:02d}": 0.95 for i in range(10)}
    agreement["doc_03"] = 0.2
    scored, _ = run(monkeypatch, agreement, 10)
    assert [s.accepted for s in scored] == [True] * 3 + [False] + [True] * 6


def test_small_pool_keeps_everything(monkeypatch):
    agreement = {"doc_00": 0.0, "doc_01": 0.0, "doc_02": 0.0}
    scored, _ = run(monkeypatch, agreement, 3)
    assert all(s.accepted for s in scored)                      # floor(0.45) = 0 may be removed


def test_uncompared_documents_keep_neutral_score(monkeypatch):
    scored, _ = run(monkeypatch, {"doc_00": None, "doc_01": 1.0}, 2)
    assert scored[0].accepted and scored[0].score_components["compared"] == 0.0


def test_figures_and_feedback_helpers():
    from qc.quality_control import _figures, format_feedback

    assert _figures("Winds of 135 knots, gusts 165, at 12:00 UTC on October 20, 2026; Signal No. 3; 1,200 people") == ["135", "165", "20", "1200"]
    assert _figures("pressure 945.5 hPa and 16.0N") == ["945.5", "16"]
    fb = format_feedback([f'x: "sentence {i}" bad' for i in range(12)] + ['x: "sentence 0" again'], max_items=3)
    assert fb.count("\n") == 3 and "(and 10 more" in fb

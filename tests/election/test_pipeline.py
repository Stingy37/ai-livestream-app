"""Offline tests for the election script pipeline: number parsing, QC rules, snapshot phase logic, TTS text fixes."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from election import qc  # noqa: E402
from election import snapshot as S  # noqa: E402
from election.facts import state_facts  # noqa: E402


def test_numbers_cjk_and_spanish():
    assert qc.numbers("約123万4567票、52.1%", "ja") == [1234567.0, 52.1]
    assert qc.numbers("约184万票，领先4.2个百分点", "zh") == [1840000.0, 4.2]
    assert qc.numbers("unos 1,84 millones de votos, el 54,8 %, 230.000 votos", "es") == [1840000.0, 54.8, 230000.0]
    # clock times and dates are not figures
    assert qc.numbers("米東部時間午後9時30分、11月18日", "ja") == [30.0]


def test_supported_rounding():
    allowed = [1840690.0, 54.8, 9.6]
    assert qc._supported(1840000, allowed)
    assert qc._supported(55, allowed)
    assert not qc._supported(61.2, allowed)
    assert not qc._supported(2500000, allowed)


def _ctx(snap, lang="ja"):
    f = state_facts(snap, lang)
    order = ["st_intro", "st_senators", "st_candidates", "st_history", "st_poll_close"]
    return {"lang": lang, "kind": "state", "phase": "preview", "facts": f, "snapshot": snap, "allowed_visuals": order, "order": order}


def test_preview_blocks_results_and_calls():
    now = datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc)
    snap = S.state_snapshot("TX", "ja", now)
    assert snap["phase"] == "preview" and not snap["results_available"]
    script = {"beats": [{"visual": "st_intro", "lines": [{"speaker": "A", "text": "パクストン氏が当選しました。", "focus": None},
                                                          {"speaker": "B", "text": "パクストン氏が55.0%でリードしています。", "focus": None}]}]}
    probs = qc.deterministic(script, _ctx(snap))
    assert any("no race has been declared" in p for p in probs)
    assert any("polls are still open" in p for p in probs)
    assert any("55" in p and "not on this beat" in p for p in probs)
    ok = {"beats": [{"visual": "st_intro", "lines": [{"speaker": "A", "text": "AP通信の勝敗判定はまだ出ていません。", "focus": None}]}]}
    assert not any("declared" in p for p in qc.deterministic(ok, _ctx(snap)))


def test_nothing_before_last_close():
    # TX main close 20:00 ET, last 21:00 ET: at 20:30 ET still preview
    snap = S.state_snapshot("TX", "es", datetime(2026, 11, 4, 1, 30, tzinfo=timezone.utc))
    assert snap["phase"] == "preview" and snap["candidates"][0]["votes"] is None


def test_banned_word_boundaries_spanish():
    snap = S.state_snapshot("TX", "es", datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc))
    s = {"beats": [{"visual": "st_candidates", "lines": [{"speaker": "A", "text": "Paxton apoya completar la barrera fronteriza.", "focus": "paxton"},
                                                           {"speaker": "B", "text": "Talarico apoya una reforma migratoria.", "focus": "talarico"}]}]}
    probs = qc.deterministic(s, _ctx(snap, "es"))
    assert not any("'barre'" in p for p in probs)


def test_voice_text_fixes():
    from election.voice import _say_es, _say_ja
    assert "ぐん" in _say_ja("タラント郡では") and "さい" in _say_ja("63歳")
    assert "点" in _say_ja("54.8%") and "くじ" in _say_ja("午後9時")
    assert "Járris" in _say_es("el condado de Harris") and "54 coma 8 por ciento" in _say_es("el 54,8 %")

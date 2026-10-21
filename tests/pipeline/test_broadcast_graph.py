"""Offline tests for graph.BroadcastGraph on the example config."""

from pathlib import Path

from graph import BroadcastGraph

CONFIG = Path(__file__).resolve().parents[2] / "saved_configs" / "example.json"


def test_example_config_builds_and_validates():
    g = BroadcastGraph.from_config(CONFIG)
    assert g.validate().is_valid
    assert [s.node_key for s in g.active_scenes()] == ["open", "position", "forecast", "impacts", "close"]
    assert all(s.id == f"sc-{s.node_key}" for s in g.active_scenes())
    assert g.scenes["impacts"].tts_voice == "am_michael"          # per-scene generation override
    assert g.scenes["open"].tts_voice == "af_heart"               # default folded in
    assert g.scene_options("impacts").do_web_search is True
    assert g.scene_options("position").do_web_search is False


def test_cycle_expansion_and_update_due():
    g = BroadcastGraph.from_config(CONFIG)
    steps = list(g.traversal())
    keys = [s.scene.node_key for s in steps]
    assert keys[0] == "open" and keys[-1] == "close"
    assert keys.count("position") == 6                            # repetitions: 6
    due = [(s.iteration, s.scene.node_key) for s in steps if s.update_due]
    assert due == [(2, "impacts"), (4, "impacts"), (6, "impacts")]  # repetitions_until_update: 2
    assert [s.id for s in g.scenes_in_cycle("c1")] == ["sc-position", "sc-forecast", "sc-impacts"]
    assert g.playlist()[:4] == ["sc-open", "sc-position", "sc-forecast", "sc-impacts"]
    assert len(g.playlist()) == 2 + 3 * 6


def test_dangling_reference_is_rejected(tmp_path):
    import json

    import pytest

    from graph.graph import ConfigError

    cfg = json.loads(CONFIG.read_text())
    cfg["graph"]["nodes"][1]["scene"]["topic_description"] = "does_not_exist"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError):
        BroadcastGraph.from_config(p)

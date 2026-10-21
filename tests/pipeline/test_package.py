"""PackageBuilder writes a valid v2 manifest with per-file hashes."""

import json
import wave

import numpy as np

from broadcast.package import PackageBuilder, SceneEntry, load_manifest, validate_manifest


def tone(path, seconds=0.5, rate=24000):
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def test_build_and_validate(tmp_path):
    wav = tmp_path / "a.wav"
    tone(wav)
    b = PackageBuilder(tmp_path / "packages", "Test config", "run-1", storm={"name": "CHAMPI"}, is_test=True)
    pdir = b.build([SceneEntry("sc-a", "a", "Scene A", 1, "Hello there.", wav, headline={"main": "Hi", "sub": "", "tag": "A"})],
                   playlist=["sc-a", "sc-a"], reason="initial")
    m = load_manifest(pdir)
    assert m["schema_version"] == 2 and m["package_id"] == pdir.name and m["playlist"] == ["sc-a", "sc-a"]
    assert m["scenes"][0]["audio"]["key"] == f"packages/{pdir.name}/sc-a.wav"
    assert abs(m["scenes"][0]["audio"]["duration_seconds"] - 0.5) < 0.01
    assert validate_manifest(m, pdir) == []
    m["playlist"].append("sc-missing")
    assert any("unknown scene" in p for p in validate_manifest(m, pdir))

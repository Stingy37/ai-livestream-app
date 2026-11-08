"""The election-night runner for one stream: keeps every scene of the playlist fresh and publishes packages.

    python -m election.run --lang ja [--stream election-ja] [--once] [--test]

Loop: write desk.json every 30 s; pick the next scene that needs (re)generation, starting with the scene after the one
on air (output/election/air/<stream>/playback.json, the page's heartbeat), so new versions land before they air;
snapshot -> writer + QC -> per-sentence TTS -> publish a package with the newest version of every scene.

A scene is regenerated when its data changed (snapshot digest) and its last version is >= MIN_REGEN_S old, when its
phase changed (polls closed, first official count, AP declaration: immediately), or when it is older than MAX_AGE_S
(fresh wording each pass, YouTube's repetitive-content rule). A failed generation keeps the previous version on air.
Stop: touch .run/STOP_ELECTION_<stream>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import secrets
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from election import snapshot as S  # noqa: E402
from election import voice, writer  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
AIR = REPO / "output" / "election" / "air"
PLAYLIST = ["national"] + S.FEATURED
MIN_REGEN_S = int(os.environ.get("ELECTION_MIN_REGEN_S", "150"))
MAX_AGE_S = int(os.environ.get("ELECTION_MAX_AGE_S", "1500"))
KEEP_PACKAGES = 6
log = logging.getLogger("election.run")


_FAKE = os.environ.get("ELECTION_FAKE_NOW")          # test only: pretend it is this instant (ISO), advancing in real time
_T0 = time.time()


def _now() -> datetime:
    if _FAKE:
        return datetime.fromtimestamp(datetime.fromisoformat(_FAKE).timestamp() + time.time() - _T0, timezone.utc)
    return datetime.now(timezone.utc)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def _digest(snap: dict) -> str:
    """What the narration depends on: drop timestamps; round numbers so tiny count changes don't force a rewrite."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("as_of", "stale", "generated_at")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        if isinstance(x, float):
            return round(x, 1)
        return x
    return hashlib.sha1(json.dumps(strip(snap), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class Stream:
    def __init__(self, lang: str, stream: str, test: bool = False) -> None:
        self.lang, self.stream, self.test = lang, stream, test
        self.dir = AIR / stream
        self.store = self.dir / "scenes"
        self.store.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        try:
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {"scenes": {}, "gen": 0}
        self.last_desk = 0.0
        self.package_id: str | None = None

    # ---------- data ----------
    def snapshot(self, key: str, now: datetime) -> dict:
        return S.national_snapshot(self.lang, now) if key == "national" else S.state_snapshot(key, self.lang, now)

    def on_air(self) -> str | None:
        try:
            pb = json.loads((self.dir / "playback.json").read_text(encoding="utf-8"))
            return str(pb.get("scene_id", "")).split("-")[0] or None
        except (OSError, ValueError):
            return None

    def order(self) -> list[str]:
        cur = self.on_air()
        if cur in PLAYLIST:
            i = PLAYLIST.index(cur)
            return PLAYLIST[i + 1:] + PLAYLIST[:i + 1]
        return list(PLAYLIST)

    def due(self, now: datetime) -> tuple[str, dict, str] | None:
        for key in self.order():
            snap = self.snapshot(key, now)
            dg = _digest(snap)
            have = self.state["scenes"].get(key)
            if not have:
                return key, snap, "new"
            age = time.time() - have["t"]                   # real seconds (now may be a test clock)
            phase = snap.get("phase") if key != "national" else None
            if key != "national" and (phase != have.get("phase") or bool(snap.get("results_available")) != have.get("results")
                                      or bool(snap.get("call")) != have.get("call")):
                return key, snap, "phase"
            if dg != have["digest"] and age >= MIN_REGEN_S:
                return key, snap, "data"
            if age >= MAX_AGE_S:
                return key, snap, "age"
        return None

    # ---------- generation ----------
    def generate(self, key: str, snap: dict, reason: str) -> bool:
        kind = "national" if key == "national" else "state"
        prev = (self.state["scenes"].get(key) or {}).get("script")
        t0 = time.time()
        script, report = writer.write_scene(kind, key, self.lang, snap, previous=prev, now=_now())
        self.state["gen"] += 1
        sid = f"{key}-{self.state['gen']}"
        _write_json(self.dir / "reports" / f"{sid}.json", {"report": report, "script": script, "reason": reason})
        if not script:
            log.warning("[%s] %s: no script passed QC (%s); keeping the previous version", self.stream, key, report.get("rounds", [])[-1:])
            if key in self.state["scenes"]:
                self.state["scenes"][key]["t"] = time.time() - MAX_AGE_S + 240      # retry in ~4 min, not in a tight loop
            return False
        t1 = time.time()
        wav = self.store / f"{sid}.wav"
        beats, dur = voice.synthesize(script, self.lang, wav)
        old = self.state["scenes"].get(key)
        self.state["scenes"][key] = {
            "scene_id": sid, "key": key, "kind": kind, "phase": snap.get("phase", "national"),
            "results": bool(snap.get("results_available")), "call": bool(snap.get("call")),
            "wav": wav.name, "duration": dur, "beats": beats, "snapshot": snap, "script": script,
            "digest": _digest(snap), "t": time.time(), "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write_json(self.state_path, self.state)
        log.info("[%s] %s (%s): %s, %.0fs audio; write %.0fs (%d rounds), tts %.0fs", self.stream, sid, reason,
                 snap.get("phase", "national"), dur, t1 - t0, len(report.get("rounds", [])), time.time() - t1)
        self.publish(f"{key} {reason}")
        if old and old.get("wav") and old["wav"] != wav.name:
            self._gc_scene(old["wav"])
        return True

    def _gc_scene(self, name: str) -> None:
        """Old scene wavs stay while a kept package still links them (hard links), so just drop the store copy."""
        try:
            (self.store / name).unlink()
        except OSError:
            pass

    # ---------- packages ----------
    def publish(self, reason: str) -> None:
        scenes = [self.state["scenes"][k] for k in PLAYLIST if k in self.state["scenes"]]
        if not scenes:
            return
        pid = f"pkg-{_now().strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"
        pdir = self.dir / pid
        pdir.mkdir(parents=True)
        out = []
        test = self.test
        for sc in scenes:
            src = self.store / sc["wav"]
            dst = pdir / sc["wav"]
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
            test = test or bool((sc["snapshot"] or {}).get("test_data"))
            out.append({"scene_id": sc["scene_id"], "key": sc["key"], "kind": sc["kind"], "phase": sc["phase"],
                        "audio": {"path": sc["wav"], "duration": sc["duration"]}, "beats": sc["beats"],
                        "snapshot": sc["snapshot"], "generated_at": sc["generated_at"]})
        manifest = {"package_id": pid, "created_at": _now().isoformat(timespec="seconds"), "lang": self.lang, "is_test": test,
                    "reason": reason, "playlist": [s["scene_id"] for s in out], "scenes": out}
        _write_json(pdir / "manifest.json", manifest)
        _write_json(self.dir / "current.json", manifest)
        self.package_id = pid
        pkgs = sorted((p for p in self.dir.iterdir() if p.is_dir() and p.name.startswith("pkg-") and p.name != pid),
                      key=lambda p: p.stat().st_mtime)
        for p in pkgs[:-(KEEP_PACKAGES - 1)]:                # oldest first, never the one just published
            shutil.rmtree(p, ignore_errors=True)

    def write_desk(self, now: datetime) -> None:
        d = S.desk(self.lang, now)
        d["is_test"] = self.test
        _write_json(self.dir / "desk.json", d)
        self.last_desk = time.time()

    # ---------- loop ----------
    def loop(self, once: bool = False) -> None:
        stop = REPO / ".run" / f"STOP_ELECTION_{self.stream}"
        if self.state["scenes"] and not (self.dir / "current.json").exists():
            self.publish("restart")
        while not stop.exists():
            now = _now()
            if time.time() - self.last_desk > 30:
                try:
                    self.write_desk(now)
                except Exception:  # noqa: BLE001
                    log.exception("[%s] desk", self.stream)
            job = self.due(now)
            if not job:
                if once:
                    return
                time.sleep(10)
                continue
            try:
                self.generate(*job)
            except Exception:  # noqa: BLE001
                log.exception("[%s] %s failed", self.stream, job[0])
                time.sleep(20)
            if once and all(k in self.state["scenes"] for k in PLAYLIST):
                return
        log.info("[%s] stop file seen", self.stream)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["es", "ja", "zh"])
    ap.add_argument("--stream")
    ap.add_argument("--once", action="store_true", help="generate every scene once, then exit")
    ap.add_argument("--test", action="store_true", help="mark packages as test data")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "openai", "urllib3", "jieba", "phonemizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    Stream(a.lang, a.stream or f"election-{a.lang}", test=a.test).loop(once=a.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())

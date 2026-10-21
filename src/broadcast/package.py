"""The broadcast package: what ICRN uploads to S3 and what the EC2 website plays.

A package is a folder ``packages/<package_id>/`` holding ``manifest.json`` plus one wav per
scene. ``manifest.json`` (schema_version 2) is a superset of the v1 manifest the EC2 side was
integration-tested with (package_id, created_at, is_test, scenes[].scene_id/version/
display_text/script.llm_output/audio.{key,duration_seconds,sample_rate,channels,format})::

    {
      "schema_version": 2,
      "package_id": "pkg-20261020T013000Z-3f9a1c",
      "created_at": "2026-10-20T01:30:00+00:00",
      "is_test": false,
      "config_name": "Typhoon Watch — Western Pacific",
      "storm": {"title": "SUPER TYPHOON", "name": "CHAMPI"},
      "generation": {"run_id": "...", "reason": "initial" | "cycle c1 update #2", "replaces": "<previous package_id>|null"},
      "playlist": ["<scene_id>", ...],               # one pass through the graph, cycles expanded; the site loops it
      "scenes": [{
          "scene_id": "...", "node_key": "position", "title": "Current Position", "version": 3,
          "display_text": "Current Position",      # short caption
          "headline": {"main": "...", "sub": "...", "tag": "CURRENT POSITION"},
          "script": {"llm_output": "...spoken text..."},
          "audio": {"key": "packages/<package_id>/<scene_id>.wav", "path": "<scene_id>.wav",
                    "duration_seconds": 51.2, "sample_rate": 24000, "channels": 1, "format": "wav",
                    "sha256": "..."},
          "sources": [{"url": "...", "source_name": "JMA", "title": "...", "published_at": "..."}],
          "qc": {"attempts": 1, "accepted": true, "score_total": 0, "contradictions": []},
          "generated_at": "..."
      }],
      "files": [{"path": "manifest.json" | "<scene_id>.wav", "key": "packages/<package_id>/<path>",
                 "size": 123, "sha256": "...", "content_type": "application/json" | "audio/wav"}]
    }

S3 keys live under ``packages/<package_id>/`` for the default stream and ``streams/<id>/packages/<package_id>/`` for a
named one (``key_prefix``, from EC2_STREAM_ID by default). The EC2 server downloads by ``path`` inside the stream's own
prefix, so a key here is informational and can never point outside the stream.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import time
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
PACKAGE_PREFIX = "packages"
_ID_RE = re.compile(r"^pkg-[0-9TZ]+-[0-9a-f]{6}$")


def new_package_id() -> str:
    return f"pkg-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{secrets.token_hex(3)}"


def is_package_id(s: str) -> bool:
    return bool(_ID_RE.match(s or ""))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path(package_dir: Path) -> Path:
    return Path(package_dir) / "manifest.json"


def wav_info(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as w:
        frames, rate, channels = w.getnframes(), w.getframerate(), w.getnchannels()
    return {"duration_seconds": round(frames / rate, 3), "sample_rate": rate, "channels": channels, "format": "wav"}


@dataclass
class SceneEntry:
    scene_id: str
    node_key: str
    title: str
    version: int
    script_text: str
    audio_src: Path                         # wav produced by the audio stage
    headline: dict[str, str] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    qc: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""


class PackageBuilder:
    """Assemble ``packages/<id>/`` from scene entries; copies wavs in and writes the manifest."""

    def __init__(self, packages_root: Path, config_name: str, run_id: str,
                 storm: dict[str, str] | None = None, is_test: bool = False, key_prefix: str | None = None) -> None:
        self.packages_root = Path(packages_root)
        stream = os.environ.get("EC2_STREAM_ID", "").strip()
        self.key_prefix = key_prefix or (f"streams/{stream}/{PACKAGE_PREFIX}" if stream and stream != "default" else PACKAGE_PREFIX)
        self.config_name = config_name
        self.run_id = run_id
        self.storm = storm or {}
        self.is_test = is_test

    def build(self, scenes: list[SceneEntry], playlist: list[str], reason: str,
              replaces: str | None = None, package_id: str | None = None) -> Path:
        package_id = package_id or new_package_id()
        pdir = self.packages_root / package_id
        if pdir.exists():
            shutil.rmtree(pdir)
        pdir.mkdir(parents=True)
        files: list[dict[str, Any]] = []
        scene_json: list[dict[str, Any]] = []
        for s in scenes:
            wav_name = f"{s.scene_id}.wav"
            dst = pdir / wav_name
            shutil.copyfile(s.audio_src, dst)
            info = wav_info(dst)
            digest = sha256_of(dst)
            key = f"{self.key_prefix}/{package_id}/{wav_name}"
            files.append({"path": wav_name, "key": key, "size": dst.stat().st_size, "sha256": digest,
                          "content_type": "audio/wav"})
            scene_json.append({
                "scene_id": s.scene_id, "node_key": s.node_key, "title": s.title, "version": s.version,
                "display_text": s.title,
                "headline": s.headline or {"main": s.title, "sub": "", "tag": s.title.upper()},
                "script": {"llm_output": s.script_text},
                "audio": {"key": key, "path": wav_name, **info, "sha256": digest},
                "sources": s.sources, "qc": s.qc,
                "generated_at": s.generated_at or _now_iso(),
            })
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "package_id": package_id,
            "created_at": _now_iso(),
            "is_test": self.is_test,
            "config_name": self.config_name,
            "storm": self.storm,
            "generation": {"run_id": self.run_id, "reason": reason, "replaces": replaces},
            "playlist": list(playlist),
            "scenes": scene_json,
            "files": files,
        }
        mpath = manifest_path(pdir)
        tmp = mpath.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, mpath)
        # the manifest describes itself last (its own hash is computed by the uploader at upload time)
        return pdir


def load_manifest(package_dir: Path) -> dict[str, Any]:
    return json.loads(manifest_path(package_dir).read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any], package_dir: Path | None = None) -> list[str]:
    """Problems found in a manifest (empty list = valid). Used by both ICRN and EC2."""
    problems: list[str] = []
    if manifest.get("schema_version") not in (1, 2):
        problems.append("unsupported schema_version")
    pid = manifest.get("package_id", "")
    if not isinstance(pid, str) or not pid:
        problems.append("missing package_id")
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        problems.append("no scenes")
        return problems
    ids = set()
    for s in scenes:
        sid = s.get("scene_id")
        if not sid or sid in ids:
            problems.append(f"bad or duplicate scene_id {sid!r}")
        ids.add(sid)
        a = s.get("audio") or {}
        for k in ("key", "duration_seconds", "sample_rate", "channels", "format"):
            if k not in a:
                problems.append(f"scene {sid}: audio.{k} missing")
        if not (s.get("script") or {}).get("llm_output"):
            problems.append(f"scene {sid}: script.llm_output missing")
        if package_dir is not None and a.get("path"):
            p = Path(package_dir) / a["path"]
            if not p.is_file():
                problems.append(f"scene {sid}: audio file {a['path']} missing")
            elif a.get("sha256") and sha256_of(p) != a["sha256"]:
                problems.append(f"scene {sid}: audio sha256 mismatch")
    for sid in manifest.get("playlist", []):
        if sid not in ids:
            problems.append(f"playlist references unknown scene {sid!r}")
    return problems


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

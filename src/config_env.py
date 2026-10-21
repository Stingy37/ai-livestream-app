"""Every runtime knob of the pipeline, read from environment variables.

scripts/run_livestream.sh is the only place that *sets* these (besides the json config);
everything else reads them through ``Settings.from_env()``. The object is a plain picklable
dataclass, so main.py can hand it to the per-scene worker processes unchanged.

Run folder layout (``RunLayout``), one folder per run under ``RUN_ROOT``::

    output/runs/<run_id>/
        run.json                       settings snapshot + config path + start time
        scenes/<scene_id>/
            sources.json               list[ScrapedDocument] as json (full Trafilatura text, untruncated)
            scrape_report.json         scraper graph trace: rounds, verify flags, expert notes/gaps
            qc_part_a.json             QCPipeline result + dynamic threshold + accepted/rejected ids
            scored.json                list[ScoredDocument] (accepted only is what RAG receives)
            index/                     sentence pool: sentences.json + e5 vectors (faiss flat index)
            context.json               RetrievedContext (the up-front retrieval)
            script_attempts.json       every draft with its ScriptScore
            script.json                ScriptOutcome
            audio.wav + audio.json     AudioAsset
        packages/<package_id>/         manifest.json + <scene_id>.wav, what gets uploaded to S3
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v == "" else v


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "y", "on")


def _env_path(name: str, default: Path) -> Path:
    return Path(_env(name, str(default))).expanduser()


@dataclass
class Settings:
    # ---- run ---------------------------------------------------------------------------
    config_path: Path = REPO_ROOT / "saved_configs" / "example.json"
    run_root: Path = REPO_ROOT / "output" / "runs"
    run_id: str = ""                      # empty -> "run-<UTC timestamp>"
    resume: bool = True                   # reuse stage artifacts already in the run folder
    max_workers: int = 4                  # scene processes per stage
    max_hours: float = 6.0                # harness stops (cleanly) after this long on air
    log_level: str = "INFO"
    publish: bool = True                  # upload packages to S3 through the EC2 endpoint
    keep_packages: int = 3                # local packages kept once EC2 reports them retired

    # ---- Lumen (UIUC) API key pool -----------------------------------------------------
    lumen_base_url: str = "https://lumen.computes.illinois.edu/v1"
    lumen_model: str = "deepseek-v4-flash"
    lumen_api_keys: str = ""              # comma / whitespace separated; LUMEN_API_KEY is also read
    lumen_keys_file: Path = REPO_ROOT / "secrets" / "lumen_keys.txt"   # one key per line, '#' comments
    lumen_timeout: float = 120.0          # seconds per request
    lumen_max_attempts: int = 12          # key rotations/retries before giving up on one request
    lumen_local_fallback: bool = True     # if every key is down, answer with the local vLLM model

    # ---- local vLLM (Qwen3-8B fp8 + dynamic-RAG LoRA) ----------------------------------
    local_llm_url: str = "http://127.0.0.1:8000/v1"
    local_llm_model: str = "qwen3-8b"
    local_llm_model_path: Path = HOME / "pre-models" / "Qwen3-8B"
    lora_name: str = "dynrag"
    local_llm_max_model_len: int = 9216
    max_tokens: int = 8192                # think block (generated + inserted) + answer
    think_fraction: float = 0.75
    max_obs_tokens: int = 1024            # one <information> block
    context_topk: int = 5                 # sentences per <information> block
    gen_temperature: float = 0.6          # Qwen3 thinking-mode sampling (grpo-rl-usal EVAL_*)
    gen_top_p: float = 0.95
    gen_top_k: int = 20

    # ---- web scraper -------------------------------------------------------------------
    searxng_url: str = "http://127.0.0.1:8890"   # 8888 is JupyterHub on ICRN
    scrape_max_threads: int = 8
    scrape_timeout: float = 25.0          # seconds per fetch
    scrape_max_pages: int = 14            # pages kept per scene (user sources always included)
    react_max_rounds: int = 3
    stale_hours: float = 6.0              # verify node flags data older than this

    # ---- QC ----------------------------------------------------------------------------
    qc_max_removed_fraction: float = 0.15 # Part A removes at most this share of the scraped pool
    qc_base_threshold: float = 0.6        # ... and never a document with agreement >= this
    nli_model_dir: Path = HOME / "pre-models" / "nli-roberta-base"
    nli_device: str = "cpu"
    script_max_attempts: int = 3
    script_score_threshold: float = 0.0   # contradictions a script may keep and still pass

    # ---- RAG ---------------------------------------------------------------------------
    e5_dir: Path = HOME / "datasets" / "models" / "e5-base-v2"
    e5_device: str = "cuda"
    retrieval_top_k: int = 5
    min_sentence_chars: int = 25

    # ---- TTS ---------------------------------------------------------------------------
    kokoro_dir: Path = HOME / "pre-models" / "Kokoro-82M"
    tts_device: str = "cuda"
    tts_default_voice: str = "af_heart"
    tts_sample_rate: int = 24000

    # ---- EC2 / S3 publishing -----------------------------------------------------------
    ec2_api_url: str = "https://54.221.147.143:8443"
    ec2_api_token_file: Path = REPO_ROOT / "secrets" / "ec2_api_token"
    ec2_ca_cert: Path = REPO_ROOT / "secrets" / "ec2_server.crt"   # pinned self-signed cert
    ec2_ssh_host: str = "ubuntu@54.221.147.143"
    ec2_ssh_key: Path = HOME / ".ssh" / "weather-dev"
    ec2_tunnel_port: int = 18443          # local port of the ssh fallback tunnel
    ec2_upload_timeout: float = 600.0

    @classmethod
    def from_env(cls) -> "Settings":
        kw = {}
        for f in dataclasses.fields(cls):
            name = f.name.upper()
            d = f.default
            if isinstance(d, bool):
                kw[f.name] = _env_bool(name, d)
            elif isinstance(d, int):
                kw[f.name] = _env_int(name, d)
            elif isinstance(d, float):
                kw[f.name] = _env_float(name, d)
            elif isinstance(d, Path):
                kw[f.name] = _env_path(name, d)
            else:
                kw[f.name] = _env(name, d)
        s = cls(**kw)
        if not s.run_id:
            s.run_id = "run-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return s

    # ---- derived ---------------------------------------------------------------------
    @property
    def think_budget(self) -> int:
        return int(self.max_tokens * self.think_fraction)

    @property
    def answer_budget(self) -> int:
        return self.max_tokens - self.think_budget

    @property
    def run_dir(self) -> Path:
        return self.run_root / self.run_id

    def layout(self) -> "RunLayout":
        return RunLayout(self.run_dir)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["lumen_api_keys"] = "<redacted>" if self.lumen_api_keys else ""
        return {k: (str(v) if isinstance(v, Path) else v) for k, v in d.items()}


@dataclass(frozen=True)
class RunLayout:
    """Paths inside one run folder (see the module docstring)."""

    run_dir: Path

    def ensure(self) -> "RunLayout":
        (self.run_dir / "scenes").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "packages").mkdir(parents=True, exist_ok=True)
        return self

    @property
    def run_json(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def packages_dir(self) -> Path:
        return self.run_dir / "packages"

    def scene_dir(self, scene_id: str) -> Path:
        d = self.run_dir / "scenes" / scene_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sources_json(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "sources.json"

    def scrape_report(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "scrape_report.json"

    def qc_part_a(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "qc_part_a.json"

    def scored_json(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "scored.json"

    def index_dir(self, scene_id: str) -> Path:
        d = self.scene_dir(scene_id) / "index"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def context_json(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "context.json"

    def script_attempts(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "script_attempts.json"

    def script_json(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "script.json"

    def audio_wav(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "audio.wav"

    def audio_json(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "audio.json"

    def judgments_json(self) -> Path:
        """LLM answers cache shared by every QC call in the run (fingerprinted by prompt + model)."""
        return self.run_dir / "qc_judgments.json"


def write_json(path: Path, data, indent: int = 2) -> None:
    """Atomic json write (temp file + rename) so a crash never leaves a half-written artifact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=indent, ensure_ascii=False, default=_json_default), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_default(o):
    import datetime as _dt

    if isinstance(o, (_dt.datetime, _dt.date)):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"not json serialisable: {type(o).__name__}")

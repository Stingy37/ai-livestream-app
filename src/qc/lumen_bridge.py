"""Glue between the QC team's simple engine (qc/simple) and the shared Lumen key pool.

``qc.simple.ner.NERExtractor`` builds its own OpenAI client from LUMEN_API_KEY. Here it is
subclassed so that every QC model call (entity extraction, the pairwise judge, the whole-passage
reads) goes through ``models.lumen`` with the same key rotation as the web scraper. The NLI
cross-encoder is loaded from the local weights folder on the CPU (the GPU is reserved for vLLM,
e5 and Kokoro).

Caches: NER records and LLM judgments are persisted per scene folder so the three script QC
rounds and a regeneration of the same scene never pay twice for the same question (the cache
key carries a fingerprint of the prompt wording and the model name, see qc/simple/nli.py).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config_env import Settings
from models import lumen
from qc.simple.ner import NERExtractor
from qc.simple.nli import NLIChecker
from qc.simple.pipeline import QCPipeline

log = logging.getLogger(__name__)


class PooledNERExtractor(NERExtractor):
    """NERExtractor whose ``ask_llm`` uses the shared key pool (rotation, cooldowns, local fallback)."""

    def __init__(self, model: str | None = None, saved_records=None, max_calls=None) -> None:
        settings = Settings.from_env()
        super().__init__(model=model or settings.lumen_model, saved_records=saved_records, max_calls=max_calls)

    def ask_llm(self, system_prompt, user_text):
        return lumen.ask(system_prompt, user_text, temperature=0.0)


class SceneQC:
    """One scene's QC toolkit: pipeline + caches persisted in the scene folder."""

    def __init__(self, scene_dir: Path | None, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.scene_dir = Path(scene_dir) if scene_dir else None
        ner_records = _load(self._ner_path) if self._ner_path else None
        judgments = _load(self._judgments_path) if self._judgments_path else None
        self.ner = PooledNERExtractor(saved_records=ner_records)
        import torch

        torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
        self.nli = NLIChecker(model_name=str(self.settings.nli_model_dir), ask_llm=self.ner.ask_llm,
                              saved_judgments=judgments, judge_model=self.ner.model)
        self.pipeline = QCPipeline(ner=self.ner, nli=self.nli)

    @property
    def _ner_path(self) -> Path | None:
        return self.scene_dir / "qc_ner.json" if self.scene_dir else None

    @property
    def _judgments_path(self) -> Path | None:
        return self.scene_dir / "qc_judgments.json" if self.scene_dir else None

    def save_caches(self) -> None:
        if not self.scene_dir:
            return
        try:
            records = [{"text": t, "entities": e} for t, e in self.ner.saved.items()]
            _dump(self._ner_path, records)
            _dump(self._judgments_path, self.nli.judgments)
        except OSError as error:
            log.warning("could not save QC caches: %s", error)

    def stats(self) -> dict:
        return {"ner_calls": self.ner.calls, "judge_calls": self.nli.llm_calls, "lumen": lumen.get_pool().status()["stats"]}


def _load(path: Path | None):
    if path and path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return None


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)

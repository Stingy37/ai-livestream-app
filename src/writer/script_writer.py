"""The script writer: one dynamic-RAG generation (writer/dynrag.py) per draft.

Called by the QC harness inside its write -> score -> rewrite loop. On the first attempt
``feedback`` is empty; on a rewrite it carries the flagged contradictions, which are appended to
the brief so the model can fix them. The scene's sentence index (saved by ``rag.Retriever``) is
loaded once per writer and retrieved from during thinking; the up-front ``RetrievedContext``
query becomes the first ``<information>`` block.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from config_env import Settings
from contracts import LLMOutput, RetrievedContext, Scene
from rag.cluster import SentenceClusterIndex
from writer.dynrag import DynRagGenerator
from writer.length import target_words


def draft_language_line(scene: Scene) -> str:
    """Non-English scenes are drafted in English (the LoRA and QC work in English); the rewriter translates."""
    import os

    from writer.rewriter import is_english, language_name

    if is_english(scene.language) or os.environ.get("REWRITE_ENABLED", "1") != "1":
        return f"Output language: {language_name(scene.language)}."
    return (f"Write this draft in English; a later step translates the final script into {language_name(scene.language)}. "
            "This overrides any output language named in the writing rules.")


def length_rule(scene: Scene) -> str:
    """The brief's word budget, derived from the duration in the scene's style rules."""
    w = target_words(scene.system_instructions)
    if not w:
        return "Keep it concise. "
    return f"The style rules' duration is about {w[0]} to {w[1]} spoken words; aim for that length, and if the sources do not support that much, stop early rather than pad. "

log = logging.getLogger(__name__)

_tokenizer = None
_tokenizer_lock = threading.Lock()


def get_tokenizer(model_path) -> Any:
    global _tokenizer
    with _tokenizer_lock:
        if _tokenizer is None:
            from transformers import AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        return _tokenizer


class WriterError(RuntimeError):
    """No draft could be produced."""


class ScriptWriter:
    """Writes one script draft for a scene from its retrieved context."""

    def __init__(self) -> None:
        self.settings = Settings.from_env()
        self._generators: dict[str, DynRagGenerator] = {}
        self.last_trace: dict[str, Any] = {}
        self._attempt = 0

    def _generator(self, scene: Scene) -> DynRagGenerator:
        g = self._generators.get(scene.id)
        if g is None:
            index = SentenceClusterIndex.load(self.settings.layout().index_dir(scene.id))
            g = DynRagGenerator(self.settings, index, get_tokenizer(self.settings.local_llm_model_path))
            self._generators[scene.id] = g
        return g

    def brief(self, scene: Scene, feedback: str = "") -> str:
        """The 'question' the Search-R1 template wraps: the segment brief, rules, and any QC feedback."""
        parts = [
            f'Write the spoken script for the segment "{scene.title}" of a live typhoon broadcast.',
            f"Segment brief: {scene.topic_description.strip()}",
            f"Writing rules: {scene.system_instructions.strip()}",
            draft_language_line(scene),
            "Look up every figure you state with the search tool and attribute it to the agency that reported it; "
            "use only figures that appear in the search results, and if a figure is missing say it has not been reported "
            "instead of inventing it. " + length_rule(scene) +
            "The script is read aloud: write figures as digits with the unit spelled out (945 hectopascals, 100 knots, "
            "16.0 degrees north, 135.6 degrees east) and write times in words (at midnight UTC on October 20), never as "
            "raw timestamps like 2026-10-20T00:00:00Z.",
        ]
        if feedback.strip():
            parts.append("A quality check of your previous draft found these problems; fix every one of them in the new draft:\n"
                         + feedback.strip())
        parts.append("What is the complete spoken script for this segment?")
        return "\n".join(parts)

    def write(self, scene: Scene, context: RetrievedContext, feedback: str = "") -> LLMOutput:
        """Write one draft. ``feedback`` is empty on the first attempt."""
        gen = self._generator(scene)
        initial_query = next(iter(context.relevant_sentences), None) or scene.topic_description
        self._attempt += 1
        last_error: Exception | None = None
        for k in range(2):
            seed = (hash((scene.id, self._attempt, k)) & 0x7FFFFFFF)
            try:
                traj = gen.generate(self.brief(scene, feedback), initial_query=initial_query, seed=seed)
            except Exception as error:  # noqa: BLE001
                last_error = error
                log.warning("[writer] %s: generation failed (%s); retrying", scene.title, error)
                continue
            text = clean_script(traj.answer or "")
            self.last_trace = {"summary": traj.summary(), "turns": traj.turns, "retrieved": traj.retrieved,
                               "brief": traj.question, "seed": seed}
            if text and looks_like_reasoning(text):
                log.warning("[writer] %s: the answer is the model's planning, not a script (%r...); retrying", scene.title, text[:80])
                text = ""
            if text:
                log.info("[writer] %s: %d words, %d searches, think %s (%.0fs)", scene.title, len(text.split()),
                         traj.n_searches, traj.think_closed, traj.generate_s)
                return LLMOutput(llm_output=text)
            log.warning("[writer] %s: empty answer (finish=%s); retrying", scene.title, traj.finish)
        raise WriterError(f"no script produced for {scene.title}: {last_error or 'empty answer twice'}")


_MD = re.compile(r"(\*\*|__|^#+\s*|^\s*[-*]\s+)", re.MULTILINE)
_TAGS = re.compile(r"</?(answer|think|search|information)>", re.IGNORECASE)


_REASONING = re.compile(r"^\s*(okay|ok|alright|first,? i|let me|i need to|i will|i'll|so,? the user|the user)\b"
                        r"|\b(the user (wants|asked|instructed)|i need to (create|write|make)|let me (check|start|draft))\b", re.IGNORECASE)


def looks_like_reasoning(text: str) -> bool:
    """True when the text talks about writing the script instead of being one (a think block that leaked
    into the answer when the budget ran out)."""
    return bool(_REASONING.search(text[:600]))


def clean_script(text: str) -> str:
    """Spoken text only: strip tags, markdown markers and stage cues; collapse whitespace."""
    text = _TAGS.sub(" ", text)
    text = _MD.sub("", text)
    text = re.sub(r"\[[^\]]{0,60}\]", " ", text)          # [MUSIC], [cut to map]
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()

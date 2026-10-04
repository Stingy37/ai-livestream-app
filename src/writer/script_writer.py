"""Contains the script writer: one LLM call that turns retrieved context into a broadcast script.

Called by the QC harness inside its write → score → judge → rewrite loop. On the first attempt
``feedback`` is empty; on a rewrite it carries the judge's feedback on what to fix.
"""

from __future__ import annotations

from contracts import LLMOutput, RetrievedContext, Scene


class ScriptWriter:
    """Writes one script draft for a scene from its retrieved context.

    Uses ``scene.script_model`` for the call, ``scene.system_instructions`` as the
    system prompt, and ``scene.language`` for the output language. Should keep the
    source attribution carried on each ``Sentence`` so the script can say who
    reported what.
    """

    def __init__(self) -> None:
        raise NotImplementedError

    def write(self, scene: Scene, context: RetrievedContext, feedback: str = "") -> LLMOutput:
        """Write one draft. ``feedback`` is empty on the first attempt."""
        raise NotImplementedError

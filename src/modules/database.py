"""Contains methods for persisting and retrieving every artifact the pipeline produces.

Stands in for the PostgreSQL + S3 split described in the Backend Data Model PRD: for now
everything is local, rooted at output/database, with large artifacts written under output/text
and output/audio. The split is preserved in the interface — structured records are queried by
scene, large artifacts are addressed by reference — so the storage backend can be swapped later
without changing any caller.

Also acts as the hand-off between pipeline stages. Because stages are separated by process
barriers, intermediates that cannot cross a process boundary as live objects (cleaned documents,
fitted cluster indices, audio) are persisted here and reloaded on the far side.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.audio import AudioAsset
from modules.cluster import SentenceClusterIndex
from modules.quality_control import ScriptScore
from modules.webscrapper import ScrapedDocument


@dataclass
class ArtifactRef:
    """A handle to a stored artifact — the only thing that crosses a process boundary.

    Stands in for the PRD's S3 key. Callers pass these around; only this module
    resolves one to bytes on disk.
    """

    scene_id: str
    kind: str  # "documents" | "cluster" | "script" | "audio"
    path: Path
    version: int = 1


class Database:
    """Public interface to the local artifact store.

    Constructed from a root path alone, and cheap to construct — each scene
    worker builds its own inside its process rather than inheriting a live
    handle across the fork. Nothing here holds an open connection.
    """

    def __init__(self, root: Path) -> None:
        raise NotImplementedError

    # ── stage 1: staged source documents ────────────────────────────────────

    def stage_documents(self, scene_id: str, documents: list[ScrapedDocument]) -> ArtifactRef:
        """Write the documents that cleared website quality control.

        This is the staging store: only accepted documents land here, so
        everything downstream can assume what it reads has already been scored.
        """
        raise NotImplementedError

    def load_staged_documents(self, scene_id: str) -> list[ScrapedDocument]:
        """Read back a scene's accepted documents for splitting and clustering."""
        raise NotImplementedError

    # ── stage 2: fitted cluster index ───────────────────────────────────────

    def save_cluster_index(self, scene_id: str, index: SentenceClusterIndex) -> ArtifactRef:
        """Persist a fitted index so the retrieval stage can load it elsewhere."""
        raise NotImplementedError

    def load_cluster_index(self, scene_id: str) -> SentenceClusterIndex:
        """Rehydrate a scene's cluster index inside the calling process."""
        raise NotImplementedError

    # ── stages 3-4: generated scripts ───────────────────────────────────────

    def save_script(self, scene_id: str, script: str, score: ScriptScore) -> ArtifactRef:
        """Store an accepted script and its score, versioned.

        Versioning is what makes cycle regeneration and rollback possible: a
        regenerated scene writes a new version rather than overwriting the one
        that may still be on air.
        """
        raise NotImplementedError

    def load_script(self, scene_id: str, version: int | None = None) -> str:
        """Load a script — the latest version unless one is named."""
        raise NotImplementedError

    # ── stage 5: audio assets ───────────────────────────────────────────────

    def save_audio(self, scene_id: str, audio: AudioAsset) -> ArtifactRef:
        """Store generated audio as a new version and mark it playable."""
        raise NotImplementedError

    def load_audio(self, scene_id: str, version: int | None = None) -> AudioAsset | None:
        """Load a scene's current audio, or None if it has none yet.

        Returning None rather than raising is deliberate — the broadcaster warns
        and advances to the next scene rather than dropping the stream.
        """
        raise NotImplementedError

    # ── lifecycle ───────────────────────────────────────────────────────────

    def clear_run(self, scene_ids: list[str] | None = None) -> None:
        """Delete in-flight generation artifacts so the next run starts clean.

        Called on cancellation or unrecoverable failure. Must not touch the saved
        broadcast configuration or anything the user authored — only artifacts
        this pipeline produced.
        """
        raise NotImplementedError

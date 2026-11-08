"""Sentence pool + vector index for one scene (internal to the RAG team).

The sentence pool is scene-wide: sentences from every accepted document go into one index so
retrieval can span sources. Units are *sentences* (the granularity the dynamic-RAG writer
retrieves at), embedded with e5-base-v2 (``models.embeddings``) into a FAISS flat inner-product
index. ``save``/``load`` persist the pool under the run folder so the writer process can retrieve
during generation without rebuilding.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np

from contracts import ScrapedDocument, Sentence

ABBREVIATIONS = ["no", "nos", "st", "mt", "gov", "dr", "approx", "e.g", "i.e", "vs", "jan", "feb", "mar", "apr",
                 "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "km", "kph", "hpa", "utc", "jst", "pht"]
_WS = re.compile(r"[ \t\r\f\v]+")
_JUNK = re.compile(r"^[\W_]*$")


@dataclass
class ClusterMatch:
    """One hit for one query vector."""

    sentence: Sentence
    similarity: float


class SentenceSplitter:
    """Punkt-based splitter (abbreviation-aware, so "Signal No. 3" stays whole) producing the scene pool."""

    def __init__(self, min_chars: int = 0) -> None:
        self.min_chars = min_chars
        self._tok = None

    def _tokenizer(self):
        if self._tok is None:
            import nltk
            from nltk.tokenize.punkt import PunktTokenizer

            try:
                tok = PunktTokenizer("english")
            except LookupError:
                nltk.download("punkt_tab", quiet=True)
                tok = PunktTokenizer("english")
            tok._params.abbrev_types.update(ABBREVIATIONS)
            self._tok = tok
        return self._tok

    def split_text(self, text: str) -> list[str]:
        """Sentences of one text. Line breaks are boundaries too (bulletins are line-based)."""
        tok = self._tokenizer()
        out: list[str] = []
        for line in text.split("\n"):
            line = _WS.sub(" ", line).strip()
            if not line or _JUNK.match(line):
                continue
            for s in tok.tokenize(line):
                s = s.strip()
                if len(s) >= self.min_chars and not _JUNK.match(s):
                    out.append(s)
        return out

    def split(self, documents: Sequence[ScrapedDocument]) -> list[Sentence]:
        """Flatten documents into one ordered pool of sentences with provenance attached."""
        pool: list[Sentence] = []
        for di, doc in enumerate(documents):
            for si, text in enumerate(self.split_text(doc.main_text)):
                pool.append(Sentence(text=text, source_url=doc.url, source_name=doc.source_name,
                                     published_at=doc.published_at, document_index=di, sentence_index=si))
        return pool


class SentenceClusterIndex:
    """The fitted vector index over one scene's sentence pool (name kept from the skeleton)."""

    def __init__(self, sentences: list[Sentence], vectors: np.ndarray, titles: dict[int, str] | None = None) -> None:
        import faiss

        self.sentences = sentences
        self.vectors = np.ascontiguousarray(vectors.astype(np.float32))
        self.titles = titles or {}
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        if len(sentences):
            self.index.add(self.vectors)

    @classmethod
    def build(cls, sentences: Sequence[Sentence], encoder=None, titles: dict[int, str] | None = None) -> "SentenceClusterIndex":
        """Embed the sentence pool (passage: prefix) and build the flat index."""
        from models.embeddings import get_encoder

        enc = encoder or get_encoder()
        texts = [s.text for s in sentences]
        vecs = enc.encode(texts, is_query=False) if texts else np.zeros((0, enc.dim), dtype=np.float32)
        return cls(list(sentences), vecs, titles)

    def query(self, vectors: Sequence[Sequence[float]], top_k: int) -> list[list[ClusterMatch]]:
        """Top-k sentences per query vector, positionally aligned with ``vectors``."""
        if not len(self.sentences) or not len(vectors):
            return [[] for _ in vectors]
        q = np.ascontiguousarray(np.asarray(vectors, dtype=np.float32))
        k = min(top_k, len(self.sentences))
        scores, ids = self.index.search(q, k)
        out = []
        for row_s, row_i in zip(scores, ids):
            hits = [ClusterMatch(self.sentences[i], float(s)) for s, i in zip(row_s, row_i) if i >= 0]
            out.append(hits)
        return out

    def search_texts(self, queries: list[str], top_k: int, encoder=None) -> list[list[ClusterMatch]]:
        from models.embeddings import get_encoder

        enc = encoder or get_encoder()
        return self.query(enc.encode(list(queries), is_query=True), top_k)

    def exemplars(self) -> dict[int, str]:
        """One representative sentence per document index (first sentence)."""
        out: dict[int, str] = {}
        for s in self.sentences:
            out.setdefault(s.document_index, s.text)
        return out

    # ---- persistence -----------------------------------------------------------------
    def save(self, path: Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        np.save(path / "vectors.npy", self.vectors)
        rows = [{"text": s.text, "source_url": s.source_url, "source_name": s.source_name,
                 "published_at": s.published_at.isoformat() if s.published_at else None,
                 "document_index": s.document_index, "sentence_index": s.sentence_index} for s in self.sentences]
        (path / "sentences.json").write_text(json.dumps({"sentences": rows, "titles": self.titles}, ensure_ascii=False),
                                             encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SentenceClusterIndex":
        path = Path(path)
        data = json.loads((path / "sentences.json").read_text(encoding="utf-8"))
        sentences = [Sentence(text=r["text"], source_url=r["source_url"], source_name=r["source_name"],
                              published_at=datetime.fromisoformat(r["published_at"]) if r["published_at"] else None,
                              document_index=r["document_index"], sentence_index=r["sentence_index"])
                     for r in data["sentences"]]
        titles = {int(k): v for k, v in data.get("titles", {}).items()}
        return cls(sentences, np.load(path / "vectors.npy"), titles)

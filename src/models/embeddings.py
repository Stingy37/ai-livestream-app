"""e5-base-v2 sentence encoder, the same conventions as the dynamic-RAG training corpus.

Mirrors grpo-rl-usal's E5QueryEncoder (Search-R1 / FlashRAG conventions): "query: " / "passage: "
prefix, mean pooling over the attention mask, L2-normalised, max_length 256. Queries and passages
must be embedded by the same model with these prefixes or they land in different spaces.

Loaded lazily, once per process (``get_encoder``).
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np


class E5Encoder:
    def __init__(self, model_dir: str | Path, device: str = "cuda", max_length: int = 256, fp16: bool = True) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.device = device if (device != "cuda" or torch.cuda.is_available()) else "cpu"
        self.max_length = max_length
        self.tok = AutoTokenizer.from_pretrained(str(model_dir))
        dtype = torch.float16 if (fp16 and self.device == "cuda") else torch.float32
        self.model = AutoModel.from_pretrained(str(model_dir), dtype=dtype).to(self.device).eval()
        self.dim = int(self.model.config.hidden_size)
        self._lock = threading.Lock()

    def encode(self, texts: list[str], batch_size: int = 64, is_query: bool = True) -> np.ndarray:
        import torch

        prefix = "query: " if is_query else "passage: "
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        with self._lock, torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch = [prefix + t for t in texts[i:i + batch_size]]
                enc = self.tok(batch, max_length=self.max_length, padding=True, truncation=True,
                               return_tensors="pt").to(self.device)
                hidden = self.model(**enc, return_dict=True).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                emb = (hidden * mask).sum(1) / mask.sum(1)
                emb = torch.nn.functional.normalize(emb.float(), dim=-1)
                out[i:i + len(batch)] = emb.cpu().numpy()
        return out


_encoder: E5Encoder | None = None
_encoder_lock = threading.Lock()


def get_encoder(model_dir: str | Path | None = None, device: str | None = None) -> E5Encoder:
    """This process's encoder (built on first use from Settings unless paths are given)."""
    global _encoder
    with _encoder_lock:
        if _encoder is None:
            if model_dir is None or device is None:
                from config_env import Settings

                s = Settings.from_env()
                model_dir = model_dir or s.e5_dir
                device = device or s.e5_device
            _encoder = E5Encoder(model_dir, device=device)
        return _encoder

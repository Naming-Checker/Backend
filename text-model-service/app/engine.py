"""Similarity search over precomputed text embeddings."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


def _parse_classes(raw: object) -> list[int]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[int] = []
    for item in parsed:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


class SemanticEncoder:
    def __init__(self, local_path: str, device: str | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.tokenizer = AutoTokenizer.from_pretrained(local_path, local_files_only=True)
        self.model = AutoModel.from_pretrained(local_path, local_files_only=True).to(self.device)
        self.model.eval()

    @torch.inference_mode()
    def encode(self, texts: list[str], batch_size: int = 64, max_length: int = 64) -> torch.Tensor:
        chunks: list[torch.Tensor] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            enc = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(self.device)
            hidden = self.model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            pooled = F.normalize(pooled, p=2, dim=1)
            chunks.append(pooled.cpu())
        return torch.cat(chunks, dim=0)


class TextSimilarityEngine:
    def __init__(
        self,
        *,
        embeddings_pt_path: str,
        embeddings_csv_path: str,
        model_path: str,
        encode_batch_size: int,
        max_length: int,
    ) -> None:
        pt_path = Path(embeddings_pt_path)
        csv_path = Path(embeddings_csv_path)
        model_dir = Path(model_path)

        if not pt_path.is_file():
            raise FileNotFoundError(f"Embeddings tensor not found: {pt_path}")
        if not csv_path.is_file():
            raise FileNotFoundError(f"Embeddings metadata CSV not found: {csv_path}")
        if not model_dir.is_dir():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        logger.info("Loading embeddings tensor from %s", pt_path)
        embeddings = torch.load(pt_path, map_location="cpu", weights_only=True)
        if embeddings.dim() != 2:
            msg = f"Expected 2D embedding matrix, got shape {tuple(embeddings.shape)}"
            raise ValueError(msg)
        self._embeddings = F.normalize(embeddings.float(), p=2, dim=1)

        logger.info("Loading sidecar metadata from %s", csv_path)
        sidecar = pd.read_csv(csv_path)
        if len(sidecar) != self._embeddings.shape[0]:
            msg = (
                f"Row count mismatch: embeddings={self._embeddings.shape[0]}, "
                f"sidecar={len(sidecar)}"
            )
            raise ValueError(msg)
        self._sidecar = sidecar

        logger.info("Loading semantic encoder from %s", model_dir)
        self._encoder = SemanticEncoder(str(model_dir))
        self._encode_batch_size = encode_batch_size
        self._max_length = max_length

    def search(self, *, query: str, mktu_codes: list[int], top_k: int) -> list[dict[str, object]]:
        query_clean = query.strip()
        if not query_clean:
            raise ValueError("Query must not be empty.")
        query_vec = self._encoder.encode(
            [query_clean], batch_size=self._encode_batch_size, max_length=self._max_length
        )
        sims = (self._embeddings @ query_vec.squeeze(0)).numpy()

        if mktu_codes:
            target = set(mktu_codes)
            classes = self._sidecar["classes_json"].apply(_parse_classes)
            mask = classes.apply(lambda cls: bool(set(cls) & target)).to_numpy()
            sims = np.where(mask, sims, -np.inf)

        finite_count = int(np.isfinite(sims).sum())
        k = min(top_k, finite_count)
        if k <= 0:
            return []

        top_idx = np.argpartition(-sims, k - 1)[:k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        results: list[dict[str, object]] = []
        for idx in top_idx:
            row = self._sidecar.iloc[int(idx)]
            cosine = float(sims[int(idx)])
            classes = _parse_classes(row.get("classes_json"))
            results.append(
                {
                    "name_clean": str(row.get("name_clean", "")),
                    "name_display": str(row.get("name_display", "") or row.get("name_clean", "")),
                    "mark_significant": str(row.get("mark_significant", "")),
                    "certificate_link": str(row.get("certificate_link", "")),
                    "mktu_codes": classes,
                    "cosine_similarity": cosine,
                    "similarity_percent": cosine * 100.0,
                }
            )
        return results

"""Similarity search over precomputed text embeddings (memory-conscious)."""

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

_ALIAS_COLUMNS = ["alias", "display_name", "certificate_link", "classes"]
_SEARCH_CHUNK = 200_000


def _parse_classes(raw: object) -> list[int]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    if isinstance(raw, (list, tuple, np.ndarray)):
        out: list[int] = []
        for item in raw:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out
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
        # float16 roughly halves CPU RAM for LaBSE (~900MB vs ~1.8GB).
        dtype = torch.float16 if self.device.type == "cpu" else torch.float16
        self.model = AutoModel.from_pretrained(
            local_path,
            local_files_only=True,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.model.eval()

    @torch.inference_mode()
    def encode(self, texts: list[str], batch_size: int = 64, max_length: int = 128) -> torch.Tensor:
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
            hidden = self.model(**enc).last_hidden_state.float()
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            pooled = F.normalize(pooled, p=2, dim=1)
            chunks.append(pooled.cpu())
        return torch.cat(chunks, dim=0)


def _load_or_build_mmap(pt_path: Path, npy_path: Path) -> np.ndarray:
    meta_path = Path(str(npy_path) + ".meta.json")
    if npy_path.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        logger.info("Opening embeddings memmap %s shape=%s", npy_path, meta["shape"])
        return np.memmap(
            npy_path,
            dtype=np.dtype(meta["dtype"]),
            mode="r",
            shape=tuple(meta["shape"]),
        )

    if not pt_path.is_file():
        raise FileNotFoundError(
            f"Need prebuilt {npy_path} (+ .meta.json) or source tensor {pt_path}"
        )

    logger.info("Building embeddings memmap from %s", pt_path)
    embeddings = torch.load(pt_path, map_location="cpu", weights_only=True, mmap=True)
    if embeddings.dim() != 2:
        raise ValueError(f"Expected 2D embedding matrix, got shape {tuple(embeddings.shape)}")
    shape = tuple(embeddings.shape)
    npy_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(npy_path) + ".tmp")
    mm = np.memmap(tmp_path, dtype=np.float16, mode="w+", shape=shape)
    step = _SEARCH_CHUNK
    for start in range(0, shape[0], step):
        end = min(start + step, shape[0])
        chunk = embeddings[start:end]
        if chunk.dtype != torch.float16:
            chunk = chunk.half()
        mm[start:end] = chunk.numpy()
        logger.info("Converted rows %s:%s / %s", start, end, shape[0])
    mm.flush()
    del mm, embeddings
    tmp_path.replace(npy_path)
    meta_path.write_text(
        json.dumps({"dtype": "float16", "shape": list(shape)}),
        encoding="utf-8",
    )
    return np.memmap(npy_path, dtype=np.float16, mode="r", shape=shape)


class TextSimilarityEngine:
    def __init__(
        self,
        *,
        embeddings_pt_path: str,
        aliases_parquet_path: str,
        class_mask_path: str,
        model_path: str,
        manifest_path: str | None = None,
        encode_batch_size: int,
        max_length: int,
        mmap_embeddings: bool = True,
        search_chunk_size: int = _SEARCH_CHUNK,
    ) -> None:
        pt_path = Path(embeddings_pt_path)
        aliases_path = Path(aliases_parquet_path)
        mask_path = Path(class_mask_path)
        model_dir = Path(model_path)

        if not aliases_path.is_file():
            raise FileNotFoundError(f"Aliases parquet not found: {aliases_path}")
        if not mask_path.is_file():
            raise FileNotFoundError(f"Class mask not found: {mask_path}")
        if not model_dir.is_dir():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        # Prefer prebuilt float16 memmap next to the .pt (same stem + .f16.npy).
        npy_path = pt_path.with_name(pt_path.stem + ".f16.npy")
        if not pt_path.is_file() and not npy_path.is_file():
            raise FileNotFoundError(
                f"Embeddings not found: need {pt_path} or {npy_path}"
            )
        if npy_path.is_file() or mmap_embeddings:
            self._embeddings = _load_or_build_mmap(pt_path, npy_path)
        else:
            tensor = torch.load(pt_path, map_location="cpu", weights_only=True)
            self._embeddings = tensor.half().numpy()

        n_rows = int(self._embeddings.shape[0])

        logger.info("Loading aliases metadata from %s", aliases_path)
        aliases = pd.read_parquet(aliases_path, columns=_ALIAS_COLUMNS)
        if len(aliases) != n_rows:
            raise ValueError(f"Row count mismatch: embeddings={n_rows}, aliases={len(aliases)}")
        self._aliases = aliases

        logger.info("Loading class mask from %s", mask_path)
        class_mask = np.load(mask_path, mmap_mode="r")
        if class_mask.shape[1] != n_rows:
            raise ValueError(
                f"Class mask column count mismatch: mask={class_mask.shape[1]}, embeddings={n_rows}"
            )
        self._class_mask = class_mask

        if manifest_path:
            manifest_file = Path(manifest_path)
            if manifest_file.is_file():
                with manifest_file.open(encoding="utf-8") as fh:
                    manifest = json.load(fh)
                expected_rows = manifest.get("rows")
                if expected_rows is not None and int(expected_rows) != n_rows:
                    raise ValueError(
                        f"Manifest row count mismatch: manifest={expected_rows}, embeddings={n_rows}"
                    )
                logger.info(
                    "Manifest ok: rows=%s, embedding_dim=%s, model=%s",
                    manifest.get("rows"),
                    manifest.get("embedding_dim"),
                    manifest.get("model_path"),
                )

        logger.info("Loading semantic encoder from %s", model_dir)
        self._encoder = SemanticEncoder(str(model_dir))
        self._encode_batch_size = encode_batch_size
        self._max_length = max_length
        self._search_chunk_size = max(10_000, search_chunk_size)

    def _mktu_mask(self, mktu_codes: list[int]) -> np.ndarray:
        mask = np.zeros(self._class_mask.shape[1], dtype=bool)
        for code in mktu_codes:
            if 0 <= code < self._class_mask.shape[0]:
                mask |= np.asarray(self._class_mask[code])
        return mask

    def search(self, *, query: str, mktu_codes: list[int], top_k: int) -> list[dict[str, object]]:
        query_clean = query.strip()
        if not query_clean:
            raise ValueError("Query must not be empty.")
        query_vec = (
            self._encoder.encode(
                [query_clean],
                batch_size=self._encode_batch_size,
                max_length=self._max_length,
            )
            .squeeze(0)
            .numpy()
            .astype(np.float32, copy=False)
        )

        n_rows = int(self._embeddings.shape[0])
        class_filter = self._mktu_mask(mktu_codes) if mktu_codes else None

        # Keep a running top-k across chunks so we never allocate a full (N,) score vector
        # that forces paging the entire embedding matrix into RAM at once.
        best_scores = np.full(top_k, -np.inf, dtype=np.float32)
        best_idx = np.full(top_k, -1, dtype=np.int64)
        filled = 0

        for start in range(0, n_rows, self._search_chunk_size):
            end = min(start + self._search_chunk_size, n_rows)
            chunk = np.asarray(self._embeddings[start:end], dtype=np.float32)
            sims = chunk @ query_vec
            if class_filter is not None:
                sims = np.where(class_filter[start:end], sims, -np.inf)

            finite = np.isfinite(sims)
            if not finite.any():
                continue
            local_k = min(top_k, int(finite.sum()))
            part = np.argpartition(-sims, local_k - 1)[:local_k]
            for li in part:
                score = float(sims[li])
                if not np.isfinite(score):
                    continue
                abs_i = start + int(li)
                if filled < top_k:
                    best_scores[filled] = score
                    best_idx[filled] = abs_i
                    filled += 1
                    if filled == top_k:
                        order = np.argsort(best_scores)
                        best_scores[:] = best_scores[order]
                        best_idx[:] = best_idx[order]
                elif score > best_scores[0]:
                    best_scores[0] = score
                    best_idx[0] = abs_i
                    order = np.argsort(best_scores)
                    best_scores[:] = best_scores[order]
                    best_idx[:] = best_idx[order]

        if filled == 0:
            return []

        order = np.argsort(-best_scores[:filled])
        results: list[dict[str, object]] = []
        for rank_i in order:
            idx = int(best_idx[rank_i])
            cosine = float(best_scores[rank_i])
            row = self._aliases.iloc[idx]
            classes = _parse_classes(row.get("classes"))
            display_name = str(row.get("display_name", "") or row.get("alias", ""))
            results.append(
                {
                    "name_clean": str(row.get("alias", "")),
                    "name_display": display_name,
                    "mark_significant": display_name,
                    "certificate_link": str(row.get("certificate_link", "")),
                    "mktu_codes": classes,
                    "cosine_similarity": cosine,
                    "similarity_percent": cosine * 100.0,
                }
            )
        return results

"""Similarity search over precomputed logo embeddings (aligned with VisualModel combined pipeline)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import torch
import torch.nn.functional as F_nn
import torchvision.transforms.functional as F_t
from safetensors.torch import load_model
from torchvision import models
from torchvision.io import read_image
from torchvision.transforms import v2 as T

from app.color_similarity import (
    analyse_colors,
    color_similarities_for_indices,
    combine_metrics,
    load_color_embeddings,
    to_distribution,
)

logger = logging.getLogger(__name__)


def _to_three_channel_chw(img: torch.Tensor) -> torch.Tensor:
    """Torchvision read_image can return 1 (L) or 4 (RGBA); VGG16 expects 3×H×W."""
    c = int(img.shape[0])
    if c == 3:
        return img
    if c == 4:
        return img[:3, ...].contiguous()
    if c == 1:
        return img.repeat(3, 1, 1)
    msg = f"Expected 1, 3, or 4 image channels, got {c}"
    raise ValueError(msg)


class SquarePad:
    def __call__(self, image: torch.Tensor) -> torch.Tensor:
        c, h, w = image.size()
        max_wh = max(w, h)
        hp = (max_wh - w) // 2 + max_wh // 10
        vp = (max_wh - h) // 2 + max_wh // 10
        padding = (hp, vp, hp, vp)
        return F_t.pad(image, padding, 1, "constant")


def image_transform() -> T.Compose:
    return T.Compose(
        [
            T.ConvertImageDtype(torch.float),
            T.RGB(),
            SquarePad(),
            T.Resize((224, 224)),
            T.Lambda(lambda x: torch.clamp(x, 0, 1)),
        ]
    )


class SimilarityEngine:
    """Loads fine-tuned (or ImageNet) VGG16 + stored embeddings; optional color re-rank."""

    def __init__(
        self,
        embeddings_pt_path: str,
        embeddings_csv_path: str,
        model_weights_path: str | None = None,
        colors_csv_path: str | None = None,
        palette_size: int = 8,
        color_rerank_pool: int = 500,
        color_workers: int = 4,
    ) -> None:
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._palette_size = palette_size
        self._color_rerank_pool = max(1, color_rerank_pool)
        self._color_workers = max(1, color_workers)

        pt = Path(embeddings_pt_path)
        csv = Path(embeddings_csv_path)
        if not pt.is_file():
            raise FileNotFoundError(f"Embeddings tensor not found: {pt}")
        if not csv.is_file():
            raise FileNotFoundError(f"Embeddings paths CSV not found: {csv}")

        logger.info("Loading embeddings tensor from %s", pt)
        self._embeddings = torch.load(pt, map_location=self._device, weights_only=False)
        if self._embeddings.dim() != 2:
            msg = f"Expected 2D embedding matrix, got shape {tuple(self._embeddings.shape)}"
            raise ValueError(msg)
        self._embeddings = self._embeddings.to(self._device)

        logger.info("Loading image paths from %s", csv)
        frame = pd.read_csv(csv, header=None, index_col=None)
        paths = frame.iloc[:, 0].tolist()
        if len(paths) != self._embeddings.shape[0]:
            msg = (
                f"Row count in CSV ({len(paths)}) does not match embedding rows "
                f"({self._embeddings.shape[0]})"
            )
            raise ValueError(msg)
        self._paths: list[str] = [str(p) for p in paths]

        weights = Path(model_weights_path) if model_weights_path else None
        if weights is not None and weights.is_file():
            logger.info("Loading fine-tuned VGG16 weights from %s", weights)
            model = models.vgg16(weights=None)
            load_model(model, str(weights))
        else:
            if model_weights_path:
                logger.warning(
                    "Model weights not found at %s; falling back to ImageNet VGG16",
                    model_weights_path,
                )
            logger.info("Loading VGG16 (ImageNet weights) on %s", self._device)
            model = models.vgg16(weights=models.VGG16_Weights.DEFAULT)
        model.eval()
        self._model = model.to(self._device)
        self._transform = image_transform()

        self._embed_colors: list[list[list[float]]] | None = None
        self._embed_weights: list[list[float]] | None = None
        if colors_csv_path:
            colors_path = Path(colors_csv_path)
            if not colors_path.is_file():
                logger.warning(
                    "Color embeddings CSV not found at %s; color re-rank disabled",
                    colors_path,
                )
            else:
                logger.info("Loading color embeddings from %s", colors_path)
                color_frame = pd.read_csv(colors_path, header=None, index_col=None)
                if len(color_frame) != len(self._paths):
                    msg = (
                        f"Color CSV rows ({len(color_frame)}) do not match path rows "
                        f"({len(self._paths)})"
                    )
                    raise ValueError(msg)
                cells = color_frame.iloc[:, 0].astype(str).tolist()
                self._embed_colors, self._embed_weights = load_color_embeddings(
                    cells, self._palette_size
                )
                logger.info("Color embeddings ready (%s rows)", len(self._embed_colors))

    @property
    def ready(self) -> bool:
        return self._model is not None and self._embeddings is not None

    @property
    def color_enabled(self) -> bool:
        return self._embed_colors is not None and self._embed_weights is not None

    def _encode_path(self, image_path: str) -> torch.Tensor:
        img = read_image(image_path)
        return self._encode_tensor(img)

    def _encode_tensor(self, image_chw: torch.Tensor) -> torch.Tensor:
        if image_chw.dim() != 3:
            msg = f"Expected CHW image tensor, got shape {tuple(image_chw.shape)}"
            raise ValueError(msg)
        _, height, width = image_chw.shape
        # Tiny uploads (e.g. 1×1) blow up VGG preprocess / inference with opaque 500s.
        if height < 8 or width < 8:
            msg = f"Image too small ({width}x{height}); minimum is 8x8 pixels"
            raise ValueError(msg)
        rgb = _to_three_channel_chw(image_chw)
        x = self._transform(rgb).unsqueeze(0).to(self._device)
        with torch.inference_mode():
            out = self._model(x).detach()
        return F_nn.normalize(out, p=2, dim=1)

    def top_k_similar(self, image_path: str, k: int) -> list[tuple[str, float, float]]:
        """
        Return top-k matches as (path, score, similarity_percent).

        Score is cosine similarity when color is disabled; otherwise the combined
        VisualModel metric (still exposed as cosine_similarity in the API for compat).
        """
        encoded = self._encode_path(image_path)
        emb = F_nn.normalize(self._embeddings, p=2, dim=1)
        basic_scores = torch.mm(encoded, emb.T).squeeze(0)
        n = int(basic_scores.numel())
        k = min(k, n)

        if not self.color_enabled:
            top = torch.topk(basic_scores, k=k, largest=True)
            result: list[tuple[str, float, float]] = []
            for val, idx in zip(top.values.tolist(), top.indices.tolist()):
                path = self._paths[int(idx)]
                cos = float(val)
                result.append((path, cos, cos * 100.0))
            return result

        assert self._embed_colors is not None and self._embed_weights is not None
        pool = min(n, max(k, self._color_rerank_pool))
        top_pool = torch.topk(basic_scores, k=pool, largest=True)
        indices = [int(i) for i in top_pool.indices.tolist()]
        basic_vals = [float(v) for v in top_pool.values.tolist()]

        info = analyse_colors(image_path, self._palette_size)
        query_colors, query_weights = to_distribution(info)
        query_colors, query_weights = _pad_query(query_colors, query_weights, self._palette_size)

        color_vals = color_similarities_for_indices(
            query_colors,
            query_weights,
            self._embed_colors,
            self._embed_weights,
            indices,
            workers=self._color_workers,
        )
        combined = combine_metrics(basic_vals, color_vals)
        order = sorted(range(len(combined)), key=lambda i: combined[i], reverse=True)[:k]

        result = []
        for i in order:
            idx = indices[i]
            score = float(combined[i])
            result.append((self._paths[idx], score, score * 100.0))
        return result


def _pad_query(
    colors: list[list[float]],
    weights: list[float],
    palette_size: int,
) -> tuple[list[list[float]], list[float]]:
    missing = palette_size - len(colors)
    if missing > 0:
        colors = colors + [[0.0, 0.0, 0.0]] * missing
        weights = weights + [0.0] * missing
    elif missing < 0:
        colors = colors[:palette_size]
        weights = weights[:palette_size]
    return colors, weights

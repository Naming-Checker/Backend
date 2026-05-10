"""Similarity search over precomputed logo embeddings (aligned with VisualModel/src/similarity.py)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import torch
import torch.nn.functional as F_nn
import torchvision.transforms.functional as F_t
from torchvision import models
from torchvision.io import read_image
from torchvision.transforms import v2 as T

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
    """Loads VGG16 + stored embeddings and scores an uploaded image."""

    def __init__(
        self,
        embeddings_pt_path: str,
        embeddings_csv_path: str,
    ) -> None:
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
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

        logger.info("Loading VGG16 (ImageNet weights) on %s", self._device)
        model = models.vgg16(weights=models.VGG16_Weights.DEFAULT)
        model.eval()
        self._model = model.to(self._device)
        self._transform = image_transform()

    @property
    def ready(self) -> bool:
        return self._model is not None and self._embeddings is not None

    def _encode_path(self, image_path: str) -> torch.Tensor:
        img = read_image(image_path)
        return self._encode_tensor(img)

    def _encode_tensor(self, image_chw: torch.Tensor) -> torch.Tensor:
        rgb = _to_three_channel_chw(image_chw)
        x = self._transform(rgb).unsqueeze(0).to(self._device)
        with torch.inference_mode():
            out = self._model(x).detach()
        return F_nn.normalize(out, p=2, dim=1)

    def top_k_similar(self, image_path: str, k: int) -> list[tuple[str, float, float]]:
        """
        Return top-k matches as (path, cosine_similarity, similarity_percent).

        Cosine similarity is in [-1, 1]; we expose percent as cosine * 100 for parity with CLI output.
        """
        encoded = self._encode_path(image_path)
        emb = F_nn.normalize(self._embeddings, p=2, dim=1)
        scores = torch.mm(encoded, emb.T).squeeze(0)
        k = min(k, scores.numel())
        top = torch.topk(scores, k=k, largest=True)
        result: list[tuple[str, float, float]] = []
        for val, idx in zip(top.values.tolist(), top.indices.tolist()):
            path = self._paths[int(idx)]
            cos = float(val)
            pct = cos * 100.0
            result.append((path, cos, pct))
        return result

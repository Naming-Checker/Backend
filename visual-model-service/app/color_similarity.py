"""Color-palette similarity (aligned with VisualModel/src/similarity_colors.py)."""

from __future__ import annotations

import ast
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

import numpy as np
from color_analysis_tool import ImageAnalyzer, ImageInfo
from scipy.stats import wasserstein_distance_nd

logger = logging.getLogger(__name__)


def analyse_colors(image_path: str, palette_size: int) -> ImageInfo:
    analyzer = ImageAnalyzer()
    return analyzer.analyze_image(image_path, max_colors=palette_size)


def to_distribution(info: ImageInfo) -> tuple[list[list[float]], list[float]]:
    values: list[list[float]] = []
    weights: list[float] = []
    for color in info.colors:
        r, g, b = color.rgb
        values.append([r / 255.0, g / 255.0, b / 255.0])
        weights.append(float(color.frequency))
    return values, weights


def _pad_palette(
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


def parse_color_embedding_cell(cell: str, palette_size: int) -> tuple[list[list[float]], list[float]]:
    colors, weights = ast.literal_eval(cell)
    return _pad_palette(list(colors), list(weights), palette_size)


def load_color_embeddings(cells: Sequence[str], palette_size: int) -> tuple[list[list[list[float]]], list[list[float]]]:
    embed_colors: list[list[list[float]]] = []
    embed_weights: list[list[float]] = []
    for cell in cells:
        colors, weights = parse_color_embedding_cell(str(cell), palette_size)
        embed_colors.append(colors)
        embed_weights.append(weights)
    return embed_colors, embed_weights


def _pair_similarity(
    args: tuple[list[list[float]], list[float], list[list[float]], list[float]],
) -> float:
    colors, weights, other_colors, other_weights = args
    distance = wasserstein_distance_nd(colors, other_colors, weights, other_weights)
    return float(1.0 / (1.0 + distance))


def color_similarities_for_indices(
    query_colors: list[list[float]],
    query_weights: list[float],
    embed_colors: list[list[list[float]]],
    embed_weights: list[list[float]],
    indices: Sequence[int],
    workers: int = 4,
) -> list[float]:
    tasks = [
        (query_colors, query_weights, embed_colors[i], embed_weights[i]) for i in indices
    ]
    if not tasks:
        return []
    workers = max(1, min(workers, len(tasks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_pair_similarity, tasks))


def combine_metrics(basic_sim: Sequence[float], color_sim: Sequence[float]) -> list[float]:
    """Blend VGG cosine with color similarity (VisualModel color-branch formula)."""
    if len(basic_sim) != len(color_sim):
        msg = f"basic/color length mismatch: {len(basic_sim)} vs {len(color_sim)}"
        raise ValueError(msg)
    if not color_sim:
        return list(basic_sim)

    median_color_sim = float(np.median(np.asarray(color_sim, dtype=np.float64)))
    k = 7.0
    m = 0.1 * (1.0 - median_color_sim)
    out: list[float] = []
    for b, c in zip(basic_sim, color_sim):
        f = (float(c) ** k) * m
        out.append(float(b) * (1.0 - f) + f * float(c))
    return out

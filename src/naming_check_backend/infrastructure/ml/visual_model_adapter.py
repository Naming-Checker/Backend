from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from naming_check_backend.shared.settings import settings


@dataclass(frozen=True, slots=True)
class VisualModelMatch:
    image_path: str
    score_percent: float


class VisualModelAdapter:
    def __init__(
        self,
        *,
        similarity_module_path: str,
        embeddings_path: str,
        top_k: int,
        score_threshold: float,
    ) -> None:
        self._similarity_module_path = Path(similarity_module_path).resolve()
        self._embeddings_path = Path(embeddings_path).resolve()
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._module: ModuleType | None = None
        self._model: Any = None
        self._embeddings: Any = None
        self._embedding_paths: list[str] = []
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> None:
        module = self._load_similarity_module()
        if not self._embeddings_path.exists():
            raise FileNotFoundError(f"Embeddings not found: {self._embeddings_path}")

        csv_path = self._embeddings_path.with_suffix(".csv")
        if not csv_path.exists():
            raise FileNotFoundError(f"Embeddings csv not found: {csv_path}")

        torch = self._require_module_dependency(module, "torch")
        pandas = self._require_module_dependency(module, "pd")
        self._embeddings = torch.load(self._embeddings_path)
        self._embedding_paths = pandas.read_csv(csv_path, header=None, index_col=None)[0].tolist()
        self._model = module.load_similarity_model()
        self._module = module
        self._is_loaded = True

    def find_similar(self, image_path: str) -> list[VisualModelMatch]:
        if not self._is_loaded:
            self.load()

        query_path = Path(image_path).resolve()
        if not query_path.exists():
            raise FileNotFoundError(f"Logo image not found: {query_path}")
        assert self._module is not None
        similarities = (
            self._module.compute_similarity(str(query_path), self._embeddings, self._model)
            .cpu()
            .numpy()
            .flatten()
        )
        if len(similarities) == 0:
            return []

        numpy = self._require_module_dependency(self._module, "np")
        top_indexes = numpy.argsort(similarities)[::-1]

        matches: list[VisualModelMatch] = []
        for idx in top_indexes:
            score = float(similarities[idx]) * 100.0
            if score < self._score_threshold:
                continue
            matches.append(
                VisualModelMatch(
                    image_path=self._embedding_paths[int(idx)],
                    score_percent=score,
                )
            )
            if len(matches) >= self._top_k:
                break
        return matches

    def _load_similarity_module(self) -> ModuleType:
        module_name = "visualmodel_similarity_runtime"
        spec = spec_from_file_location(module_name, self._similarity_module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load similarity module at {self._similarity_module_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _require_module_dependency(module: ModuleType, attr_name: str) -> Any:
        dependency = getattr(module, attr_name, None)
        if dependency is None:
            raise RuntimeError(f"VisualModel module is missing required dependency `{attr_name}`.")
        return dependency


def build_visual_model_adapter() -> VisualModelAdapter:
    return VisualModelAdapter(
        similarity_module_path=settings.visualmodel_similarity_module_path,
        embeddings_path=settings.visualmodel_embeddings_path,
        top_k=settings.visualmodel_top_k,
        score_threshold=settings.visualmodel_score_threshold,
    )

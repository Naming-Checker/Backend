from pathlib import Path
from typing import Protocol

from naming_check_backend.domain.entities import (
    CheckRequest,
    ConflictResultSet,
    FlowType,
    LogoComparisonPayload,
    MatchCandidate,
    ProcessingStatus,
)
from naming_check_backend.domain.policies import build_similarity_score, rank_candidates
from naming_check_backend.domain.value_objects import LogoAssetRef, MktuClassSet
from naming_check_backend.infrastructure.ml.visual_model_adapter import VisualModelMatch
from naming_check_backend.shared.settings import settings


class LogoSimilarityAdapter(Protocol):
    def find_similar(self, image_path: str) -> list[VisualModelMatch]: ...


class LogoComparisonUseCase:
    """Orchestrates the logo comparison flow."""

    def __init__(self, visual_model_adapter: LogoSimilarityAdapter | None = None) -> None:
        self._visual_model_adapter = visual_model_adapter

    def execute(
        self,
        reference_logo: LogoAssetRef,
        suspicious_logo: LogoAssetRef,
        mktu_codes: list[int],
    ) -> tuple[CheckRequest, ConflictResultSet, str]:
        request_suffix = reference_logo.asset_ref.rsplit("/", maxsplit=1)[-1]
        request_id = f"logo-{request_suffix}-001"
        mktu_set = MktuClassSet.from_iterable(mktu_codes)
        request = CheckRequest(
            request_id=request_id,
            flow=FlowType.LOGO_COMPARISON,
            status=ProcessingStatus.COMPLETED,
            mktu_codes=mktu_set,
            payload=LogoComparisonPayload(
                reference_logo=reference_logo,
                suspicious_logo=suspicious_logo,
            ),
        )
        candidates = self._build_candidates(reference_logo, mktu_set)
        ranked = tuple(rank_candidates(candidates))
        summary = self._build_summary()
        return request, ConflictResultSet(request_id=request_id, candidates=ranked), summary

    def _build_candidates(self, reference_logo: LogoAssetRef, mktu_set: MktuClassSet) -> list[MatchCandidate]:
        if self._visual_model_adapter is None:
            return self._placeholder_candidates(mktu_set)
        query_image_path = self._resolve_asset_ref(reference_logo.asset_ref)
        matches = self._visual_model_adapter.find_similar(query_image_path)
        if not matches:
            return self._placeholder_candidates(mktu_set)
        return [self._to_domain_match(match, mktu_set, idx) for idx, match in enumerate(matches, start=1)]

    def _to_domain_match(
        self, match: VisualModelMatch, mktu_set: MktuClassSet, position: int
    ) -> MatchCandidate:
        candidate_name = Path(match.image_path).name
        return MatchCandidate(
            candidate_id=f"logo-{position:03d}",
            candidate_name=candidate_name,
            source=settings.visualmodel_source,
            mktu_codes=mktu_set,
            similarity=build_similarity_score(match.score_percent, visual=match.score_percent),
            summary="Visual similarity match from VisualModel embedding index.",
        )

    @staticmethod
    def _placeholder_candidates(mktu_set: MktuClassSet) -> list[MatchCandidate]:
        return [
            MatchCandidate(
                candidate_id="logo-001",
                candidate_name="Internal similar visual mark",
                source="trademark_db",
                mktu_codes=mktu_set,
                similarity=build_similarity_score(88.6, visual=88.6, legal=85.0),
                summary="Similar visual silhouette and retained text element.",
            )
        ]

    @staticmethod
    def _resolve_asset_ref(asset_ref: str) -> str:
        if asset_ref.startswith("file://"):
            path = Path(asset_ref.removeprefix("file://")).expanduser().resolve()
            return str(path)
        if asset_ref.startswith("logo://"):
            relative_path = asset_ref.removeprefix("logo://")
            path = Path(settings.visualmodel_assets_root).expanduser().resolve() / relative_path
            return str(path)
        path = Path(asset_ref).expanduser().resolve()
        return str(path)

    def _build_summary(self) -> str:
        if self._visual_model_adapter is None:
            return (
                "Placeholder Stage 1 response with internal logo matches. Final file transport "
                "format will be уточнен separately."
            )
        return "Stage 1 logo comparison produced by in-process VisualModel adapter."

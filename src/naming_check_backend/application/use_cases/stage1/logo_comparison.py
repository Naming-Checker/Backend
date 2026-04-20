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


class LogoComparisonUseCase:
    """Orchestrates the logo comparison flow."""

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
        candidates = [
            MatchCandidate(
                candidate_id="logo-001",
                candidate_name="Internal similar visual mark",
                source="trademark_db",
                mktu_codes=mktu_set,
                similarity=build_similarity_score(88.6, visual=88.6, legal=85.0),
                summary="Similar visual silhouette and retained text element.",
            )
        ]
        ranked = tuple(rank_candidates(candidates))
        summary = (
            "Placeholder Stage 1 response with internal logo matches. Final file transport "
            "format will be уточнен separately."
        )
        return request, ConflictResultSet(request_id=request_id, candidates=ranked), summary

from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    FlowType,
    LogoComparisonRequest,
    LogoComparisonResponse,
    MatchCandidate,
    ProcessingStatus,
    SimilarityBreakdown,
    Stage1Meta,
    Stage2StatusInfo,
)

router = APIRouter()
use_case = LogoComparisonUseCase()


@router.post(
    "",
    response_model=LogoComparisonResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Submit logo comparison",
    description=(
        "Accepts placeholder logo references, returns internal visual matches for Stage 1, "
        "and publishes the Stage 2 webhook contract for later external enrichment."
    ),
)
def submit_logo_comparison(payload: LogoComparisonRequest) -> LogoComparisonResponse:
    request_id = f"logo-{payload.reference_logo.asset_ref.rsplit('/', maxsplit=1)[-1]}-001"
    internal_results = [
        MatchCandidate(
            candidate_id="logo-001",
            candidate_name="Internal similar visual mark",
            source="trademark_db",
            mktu_codes=payload.mktu_codes,
            similarity=88.6,
            summary="Similar visual silhouette and retained text element.",
            similarity_breakdown=SimilarityBreakdown(
                visual=88.6,
                legal=85.0,
            ),
        )
    ]
    return LogoComparisonResponse(
        request_id=request_id,
        flow=FlowType.LOGO_COMPARISON,
        status=ProcessingStatus.COMPLETED,
        reference_logo=payload.reference_logo,
        suspicious_logo=payload.suspicious_logo,
        mktu_codes=payload.mktu_codes,
        internal_results=internal_results,
        comparison_summary=(
            "Placeholder Stage 1 response with internal logo matches. Final file transport "
            "format will be уточнен separately."
        ),
        stage2=Stage2StatusInfo(
            status=ProcessingStatus.ACCEPTED,
            correlation_id=request_id,
        ),
        meta=Stage1Meta(
            internal_result_count=len(internal_results),
            stage2_enabled=True,
        ),
    )

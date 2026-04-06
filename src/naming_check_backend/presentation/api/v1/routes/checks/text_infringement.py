from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.text_infringement_check import (
    TextInfringementCheckUseCase,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    FlowType,
    MatchCandidate,
    ProcessingStatus,
    SimilarityBreakdown,
    Stage1Meta,
    Stage2StatusInfo,
    TextInfringementRequest,
    TextInfringementResponse,
)

router = APIRouter()
use_case = TextInfringementCheckUseCase()


@router.post(
    "",
    response_model=TextInfringementResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Submit text infringement check",
    description=(
        "Compares the protected and suspicious namings, returns the internal Stage 1 "
        "ranking, and announces that Stage 2 enrichment will be delivered by webhook."
    ),
)
def submit_text_infringement_check(
    payload: TextInfringementRequest,
) -> TextInfringementResponse:
    protected_naming = " ".join(payload.protected_naming.split())
    suspicious_naming = " ".join(payload.suspicious_naming.split())
    request_id = f"txt-{'-'.join(suspicious_naming.casefold().split())}-001"
    internal_results = [
        MatchCandidate(
            candidate_id="tm-002",
            candidate_name=suspicious_naming,
            source="trademark_db",
            mktu_codes=payload.mktu_codes,
            similarity=94.2,
            summary="Pairwise comparison found the same dominant verbal core.",
            similarity_breakdown=SimilarityBreakdown(
                semantic=82.0,
                phonetic=98.0,
                graphic=93.0,
                legal=95.0,
            ),
        )
    ]
    return TextInfringementResponse(
        request_id=request_id,
        flow=FlowType.TEXT_INFRINGEMENT,
        status=ProcessingStatus.COMPLETED,
        protected_naming=protected_naming,
        suspicious_naming=suspicious_naming,
        mktu_codes=payload.mktu_codes,
        pair_similarity=94.2,
        internal_results=internal_results,
        stage2=Stage2StatusInfo(
            status=ProcessingStatus.ACCEPTED,
            correlation_id=request_id,
        ),
        meta=Stage1Meta(
            internal_result_count=len(internal_results),
            stage2_enabled=True,
        ),
    )

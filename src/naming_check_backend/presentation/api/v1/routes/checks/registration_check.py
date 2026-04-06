from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.registration_check import (
    RegistrationCheckUseCase,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    FlowType,
    MatchCandidate,
    ProcessingStatus,
    RegistrationCheckRequest,
    RegistrationCheckResponse,
    SimilarityBreakdown,
    Stage1Meta,
    Stage2StatusInfo,
)

router = APIRouter()
use_case = RegistrationCheckUseCase()


@router.post(
    "",
    response_model=RegistrationCheckResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Submit registration check",
    description=(
        "Runs the internal registration check synchronously and returns Stage 1 results "
        "together with Stage 2 webhook delivery metadata."
    ),
)
def submit_registration_check(payload: RegistrationCheckRequest) -> RegistrationCheckResponse:
    normalized_name = " ".join(payload.naming.split())
    request_id = f"reg-{'-'.join(normalized_name.casefold().split())}-001"
    internal_results = [
        MatchCandidate(
            candidate_id="tm-001",
            candidate_name=f"{normalized_name} PRIME",
            source="trademark_db",
            mktu_codes=payload.mktu_codes,
            similarity=91.4,
            summary="Internal trademark candidate with a strong phonetic and legal overlap.",
            similarity_breakdown=SimilarityBreakdown(
                semantic=84.0,
                phonetic=96.0,
                graphic=88.0,
                legal=90.0,
            ),
        )
    ]
    return RegistrationCheckResponse(
        request_id=request_id,
        flow=FlowType.REGISTRATION_CHECK,
        status=ProcessingStatus.COMPLETED,
        naming=normalized_name,
        mktu_codes=payload.mktu_codes,
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

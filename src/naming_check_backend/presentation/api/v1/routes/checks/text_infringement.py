from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.text_infringement_check import (
    TextInfringementCheckUseCase,
)
from naming_check_backend.domain.entities import TextInfringementPayload
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    TextInfringementRequest,
    TextInfringementResponse,
)
from naming_check_backend.presentation.schemas.mappers import (
    to_flow_type,
    to_match_candidate,
    to_processing_status,
    to_stage1_meta,
    to_stage2_status,
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
    check_request, result_set, pair_similarity = use_case.execute(
        payload.protected_naming,
        payload.suspicious_naming,
        payload.mktu_codes,
    )
    payload_data = check_request.payload
    if not isinstance(payload_data, TextInfringementPayload):
        raise TypeError("Unexpected payload type for text_infringement flow.")
    return TextInfringementResponse(
        request_id=check_request.request_id,
        flow=to_flow_type(check_request),
        status=to_processing_status(check_request),
        protected_naming=payload_data.protected_naming.raw.strip(),
        suspicious_naming=payload_data.suspicious_naming.raw.strip(),
        mktu_codes=check_request.mktu_codes.as_list(),
        pair_similarity=pair_similarity.total,
        internal_results=[to_match_candidate(candidate) for candidate in result_set.candidates],
        stage2=to_stage2_status(check_request),
        meta=to_stage1_meta(result_set),
    )

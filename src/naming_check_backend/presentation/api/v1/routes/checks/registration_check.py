from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.registration_check import (
    RegistrationCheckUseCase,
)
from naming_check_backend.domain.entities import RegistrationPayload
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    RegistrationCheckRequest,
    RegistrationCheckResponse,
)
from naming_check_backend.presentation.schemas.mappers import (
    to_flow_type,
    to_match_candidate,
    to_processing_status,
    to_stage1_meta,
    to_stage2_status,
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
    check_request, result_set = use_case.execute(payload.naming, payload.mktu_codes)
    payload_data = check_request.payload
    if not isinstance(payload_data, RegistrationPayload):
        raise TypeError("Unexpected payload type for registration_check flow.")
    return RegistrationCheckResponse(
        request_id=check_request.request_id,
        flow=to_flow_type(check_request),
        status=to_processing_status(check_request),
        naming=payload_data.naming.raw.strip(),
        mktu_codes=check_request.mktu_codes.as_list(),
        internal_results=[to_match_candidate(candidate) for candidate in result_set.candidates],
        stage2=to_stage2_status(check_request),
        meta=to_stage1_meta(result_set),
    )

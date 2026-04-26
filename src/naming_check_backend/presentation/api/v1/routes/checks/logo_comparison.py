from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.domain.entities import LogoComparisonPayload
from naming_check_backend.presentation.api.dependencies import (
    COMMON_ERROR_RESPONSES,
    get_logo_comparison_use_case,
)
from naming_check_backend.presentation.schemas import (
    LogoComparisonRequest,
    LogoComparisonResponse,
)
from naming_check_backend.presentation.schemas.mappers import (
    to_flow_type,
    to_logo_asset_ref,
    to_match_candidate,
    to_processing_status,
    to_stage1_meta,
    to_stage2_status,
)

router = APIRouter()


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
def submit_logo_comparison(
    payload: LogoComparisonRequest,
    use_case: Annotated[LogoComparisonUseCase, Depends(get_logo_comparison_use_case)],
) -> LogoComparisonResponse:
    try:
        check_request, result_set, comparison_summary = use_case.execute(
            to_logo_asset_ref(payload.reference_logo),
            to_logo_asset_ref(payload.suspicious_logo),
            payload.mktu_codes,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    payload_data = check_request.payload
    if not isinstance(payload_data, LogoComparisonPayload):
        raise TypeError("Unexpected payload type for logo_comparison flow.")
    return LogoComparisonResponse(
        request_id=check_request.request_id,
        flow=to_flow_type(check_request),
        status=to_processing_status(check_request),
        reference_logo=payload.reference_logo.model_copy(
            update={
                "asset_ref": payload_data.reference_logo.asset_ref,
                "media_type": payload_data.reference_logo.media_type,
                "filename": payload_data.reference_logo.filename,
            }
        ),
        suspicious_logo=payload.suspicious_logo.model_copy(
            update={
                "asset_ref": payload_data.suspicious_logo.asset_ref,
                "media_type": payload_data.suspicious_logo.media_type,
                "filename": payload_data.suspicious_logo.filename,
            }
        ),
        mktu_codes=check_request.mktu_codes.as_list(),
        internal_results=[to_match_candidate(candidate) for candidate in result_set.candidates],
        comparison_summary=comparison_summary,
        stage2=to_stage2_status(check_request),
        meta=to_stage1_meta(result_set),
    )

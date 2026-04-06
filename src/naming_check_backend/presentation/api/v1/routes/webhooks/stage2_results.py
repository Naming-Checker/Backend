from fastapi import APIRouter, status

from naming_check_backend.application.use_cases.stage2.webhook_callback_processing import (
    WebhookCallbackProcessingUseCase,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import Stage2WebhookRequest, Stage2WebhookResponse

router = APIRouter()
use_case = WebhookCallbackProcessingUseCase()


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Stage2WebhookResponse,
    responses=COMMON_ERROR_RESPONSES,
    summary="Accept Stage 2 webhook result batch",
    description=(
        "Receives partial or final Stage 2 batches from the async pipeline. "
        "The endpoint is idempotent by `correlation_id` and accepts unordered deliveries."
    ),
)
def receive_stage2_result(payload: Stage2WebhookRequest) -> Stage2WebhookResponse:
    return Stage2WebhookResponse(
        correlation_id=payload.correlation_id,
        partial=payload.partial,
        use_case=use_case.__class__.__name__,
    )

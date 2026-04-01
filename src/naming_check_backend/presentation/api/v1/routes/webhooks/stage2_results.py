from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from naming_check_backend.application.use_cases.stage2.webhook_callback_processing import (
    WebhookCallbackProcessingUseCase,
)

router = APIRouter()
use_case = WebhookCallbackProcessingUseCase()


class Stage2ResultCallbackPayload(BaseModel):
    correlation_id: str
    naming: str
    mktu_codes: list[int] = Field(default_factory=list)
    partial: bool = True


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def receive_stage2_result(payload: Stage2ResultCallbackPayload) -> dict[str, object]:
    return {
        "status": "accepted",
        "delivery": "webhook",
        "partial": payload.partial,
        "use_case": use_case.__class__.__name__,
    }

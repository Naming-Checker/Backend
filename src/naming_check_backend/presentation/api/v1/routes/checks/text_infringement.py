from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.text_infringement_check import (
    TextInfringementCheckUseCase,
)

router = APIRouter()
use_case = TextInfringementCheckUseCase()


@router.post("")
def submit_text_infringement_check() -> dict[str, str]:
    return {
        "status": "not_implemented",
        "flow": "stage1_text_infringement_check",
        "use_case": use_case.__class__.__name__,
    }

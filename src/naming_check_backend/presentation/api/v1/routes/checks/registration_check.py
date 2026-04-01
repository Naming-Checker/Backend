from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.registration_check import (
    RegistrationCheckUseCase,
)

router = APIRouter()
use_case = RegistrationCheckUseCase()


@router.post("")
def submit_registration_check() -> dict[str, str]:
    return {
        "status": "not_implemented",
        "flow": "stage1_registration_check",
        "use_case": use_case.__class__.__name__,
    }

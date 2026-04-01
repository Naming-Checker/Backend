from fastapi import APIRouter

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase

router = APIRouter()
use_case = LogoComparisonUseCase()


@router.post("")
def submit_logo_comparison() -> dict[str, str]:
    return {
        "status": "not_implemented",
        "flow": "stage1_logo_comparison",
        "use_case": use_case.__class__.__name__,
    }

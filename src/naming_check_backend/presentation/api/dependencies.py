"""API dependencies."""

from typing import Any

from fastapi import Request, status

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.presentation.schemas import ErrorResponse

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "Malformed business payload.",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Conflict with current processing state.",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Schema validation failed.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Unexpected backend failure.",
    },
}

_default_logo_use_case = LogoComparisonUseCase()


def get_logo_comparison_use_case(request: Request) -> LogoComparisonUseCase:
    return getattr(request.app.state, "logo_comparison_use_case", _default_logo_use_case)

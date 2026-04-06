"""API dependencies."""

from typing import Any

from fastapi import status

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

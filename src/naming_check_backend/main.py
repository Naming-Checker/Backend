from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naming_check_backend.presentation.api.router import api_router
from naming_check_backend.presentation.middleware import RequestLoggingMiddleware
from naming_check_backend.shared.json_logging import configure_json_logging
from naming_check_backend.shared.settings import settings

configure_json_logging(
    service_name="naming-check-backend",
    env=settings.app_env,
    level=settings.log_level,
)

app = FastAPI(title=settings.app_name)


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


allowed_origins = _parse_csv(settings.cors_allow_origins)
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=_parse_csv(settings.cors_allow_methods) or ["*"],
        allow_headers=_parse_csv(settings.cors_allow_headers) or ["*"],
    )

app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)

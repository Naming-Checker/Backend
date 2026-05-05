from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.infrastructure.ml.visual_model_adapter import build_visual_model_adapter
from naming_check_backend.presentation.api.router import api_router
from naming_check_backend.shared.settings import settings

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

app.include_router(api_router)


@app.on_event("startup")
def configure_logo_comparison_use_case() -> None:
    if settings.visualmodel_enabled:
        adapter = build_visual_model_adapter()
        adapter.load()
        app.state.logo_comparison_use_case = LogoComparisonUseCase(visual_model_adapter=adapter)
        return
    app.state.logo_comparison_use_case = LogoComparisonUseCase()

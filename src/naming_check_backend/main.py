from fastapi import FastAPI

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.infrastructure.ml.visual_model_adapter import build_visual_model_adapter
from naming_check_backend.presentation.api.router import api_router
from naming_check_backend.shared.settings import settings

app = FastAPI(title=settings.app_name)
app.include_router(api_router)


@app.on_event("startup")
def configure_logo_comparison_use_case() -> None:
    if settings.visualmodel_enabled:
        adapter = build_visual_model_adapter()
        adapter.load()
        app.state.logo_comparison_use_case = LogoComparisonUseCase(visual_model_adapter=adapter)
        return
    app.state.logo_comparison_use_case = LogoComparisonUseCase()

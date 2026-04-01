from fastapi import APIRouter

from naming_check_backend.presentation.api.v1.routes.health import router as health_router
from naming_check_backend.presentation.api.v1.routes.checks.logo_comparison import router as logo_router
from naming_check_backend.presentation.api.v1.routes.checks.registration_check import (
    router as registration_router,
)
from naming_check_backend.presentation.api.v1.routes.checks.text_infringement import (
    router as text_infringement_router,
)
from naming_check_backend.presentation.api.v1.routes.webhooks.stage2_results import (
    router as stage2_results_router,
)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(registration_router, prefix="/registration-check", tags=["registration-check"])
v1_router.include_router(text_infringement_router, prefix="/text-infringement", tags=["text-infringement"])
v1_router.include_router(logo_router, prefix="/logo-comparison", tags=["logo-comparison"])
v1_router.include_router(stage2_results_router, prefix="/webhooks/stage2-results", tags=["stage2-results"])

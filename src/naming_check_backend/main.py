from fastapi import FastAPI

from naming_check_backend.presentation.api.router import api_router
from naming_check_backend.shared.settings import settings

app = FastAPI(title=settings.app_name)
app.include_router(api_router)

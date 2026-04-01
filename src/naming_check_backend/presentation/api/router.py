from fastapi import APIRouter

from naming_check_backend.presentation.api.v1.router import v1_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/api")

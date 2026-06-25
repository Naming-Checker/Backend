from fastapi import APIRouter

from naming_check_backend.shared.prometheus_metrics import set_service_health

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    set_service_health(healthy=True)
    return {"status": "ok"}

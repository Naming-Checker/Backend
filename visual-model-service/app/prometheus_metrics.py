"""Prometheus HTTP metrics — uniform schema across naming-check services."""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["service", "method", "handler", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["service", "method", "handler", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

SERVICE_HEALTH_STATUS = Gauge(
    "service_health_status",
    "1 if service reports healthy, 0 otherwise.",
    ["service"],
)

_service_name: str | None = None


def _group_status(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _handler_name(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return request.url.path


def _is_metrics_path(path: str) -> bool:
    return path.rstrip("/") == "/metrics"


def set_service_health(*, healthy: bool) -> None:
    if _service_name is None:
        return
    SERVICE_HEALTH_STATUS.labels(service=_service_name).set(1 if healthy else 0)


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if _is_metrics_path(request.url.path):
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            labels = {
                "service": self._service_name,
                "method": request.method,
                "handler": _handler_name(request),
                "status": _group_status(status_code),
            }
            HTTP_REQUESTS_TOTAL.labels(**labels).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration)


def configure_prometheus_metrics(app: FastAPI, *, service_name: str) -> None:
    global _service_name
    _service_name = service_name
    app.add_middleware(PrometheusMiddleware, service_name=service_name)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    SERVICE_HEALTH_STATUS.labels(service=service_name).set(0)

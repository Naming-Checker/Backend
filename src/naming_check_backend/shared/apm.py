"""Optional Elastic APM distributed tracing."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def is_apm_enabled() -> bool:
    return os.environ.get("ELASTIC_APM_ENABLED", "").lower() in {"1", "true", "yes"}


def append_trace_context(payload: dict[str, Any]) -> None:
    """Add ECS trace fields so logs link to APM transactions in Kibana."""
    if not is_apm_enabled():
        return
    try:
        import elasticapm

        trace_id = elasticapm.get_trace_id()
        transaction_id = elasticapm.get_transaction_id()
        if trace_id:
            payload["trace.id"] = trace_id
        if transaction_id:
            payload["transaction.id"] = transaction_id
    except Exception:
        return


def label_current_transaction(**labels: object) -> None:
    if not is_apm_enabled():
        return
    try:
        import elasticapm

        if elasticapm.get_client():
            elasticapm.label(**{key: value for key, value in labels.items() if value is not None})
    except Exception:
        return


def configure_apm(app: FastAPI, *, service_name: str) -> None:
    if not is_apm_enabled():
        logger.info("Elastic APM disabled (set ELASTIC_APM_ENABLED=true to enable)")
        return

    try:
        from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
        from starlette.routing import Match, Mount
    except ImportError:
        logger.warning("elastic-apm is not installed; tracing disabled")
        return

    class SafeElasticAPM(ElasticAPM):
        """ElasticAPM middleware compatible with FastAPI 0.137+ nested routers."""

        def get_route_name(self, request):  # type: ignore[no-untyped-def]
            try:
                return super().get_route_name(request) or request.url.path
            except AttributeError:
                return request.url.path

        def _get_route_name(self, scope, routes, route_name=None):  # type: ignore[no-untyped-def]
            for route in routes:
                match, child_scope = route.matches(scope)
                if match == Match.FULL:
                    route_path = getattr(route, "path", None)
                    if route_path is None:
                        return scope.get("path")
                    route_name = route_path
                    child_scope = {**scope, **child_scope}
                    nested_routes = getattr(route, "routes", None)
                    if isinstance(route, Mount) and nested_routes:
                        child_route_name = self._get_route_name(child_scope, nested_routes, route_name)
                        if child_route_name is None:
                            route_name = None
                        else:
                            route_name += child_route_name
                    return route_name
                if match == Match.PARTIAL and route_name is None:
                    route_name = getattr(route, "path", None)
            return route_name

    server_url = os.environ.get("ELASTIC_APM_SERVER_URL", "http://apm-server:8200")
    environment = os.environ.get("ELASTIC_APM_ENVIRONMENT") or os.environ.get("APP_ENV", "local")
    client = make_apm_client(
        {
            "SERVICE_NAME": os.environ.get("ELASTIC_APM_SERVICE_NAME", service_name),
            "SERVER_URL": server_url,
            "ENVIRONMENT": environment,
            "TRANSACTION_SAMPLE_RATE": float(os.environ.get("ELASTIC_APM_TRANSACTION_SAMPLE_RATE", "1.0")),
            "CAPTURE_BODY": os.environ.get("ELASTIC_APM_CAPTURE_BODY", "errors"),
            "USE_ELASTIC_TRACEPARENT_HEADER": True,
            "ENABLED": True,
        }
    )
    if client is None:
        return

    app.add_middleware(SafeElasticAPM, client=client)  # type: ignore[arg-type]
    logger.info("Elastic APM enabled", extra={"apm_server_url": server_url})
